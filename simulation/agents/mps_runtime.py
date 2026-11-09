"""Local Qwen + saved LoRA inference. No shopper state or action application."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import threading
from time import perf_counter
import zipfile

BASE_MODEL = 'Qwen/Qwen2.5-7B-Instruct'
MODEL = 'qwen2.5-7b-pilot-mps'
SETTINGS = {'max_output_tokens':256, 'do_sample':False, 'device':'mps',
    'quantization':'quanto-int4', 'activation_dtype':'float16',
    'unpack_kernel':'reference-tensor-ops-mps',
    'max_context_tokens':16384, 'prefill_chunk_tokens':256,
    'request_seed_supported':False, 'decision_mode':'single_action'}
PRICING = {'model':MODEL,'source':'local MPS inference','as_of':'2026-11-04',
    'input_usd_per_million':0,'cached_usd_per_million':0,'output_usd_per_million':0,
    'cost_basis':'No per-token API charge. Local hardware, electricity and compute costs are unmeasured.'}

_mps_library=None


def configure_mps_quantization():
    """Quanto's reference unpack algorithm, entirely on MPS; no JIT C++ extension.

    Quanto 0.2.7's compiled extension is incompatible with the installed PyTorch.
    The published reference algorithm supports MPS integer division explicitly.
    Retain the Library handle so PyTorch keeps this kernel registered.
    """
    global _mps_library
    if _mps_library is not None:return
    import torch
    import optimum.quanto  # Register the operator before its MPS implementation.
    def unpack(packed,bits):
        return torch.cat([(packed & (2**(bits*(i+1))-1))//(2**(bits*i))
            for i in range(8//bits)]).to(torch.uint8)
    _mps_library=torch.library.Library('quanto','IMPL','MPS')
    _mps_library.impl('unpack',unpack)


def sha256(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda:handle.read(1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()


def prepare_adapter(archive, destination):
    """Extract only data files into content-addressed local storage; never execute ZIP code."""
    archive=Path(archive);destination=Path(destination)
    archive_hash=sha256(archive);target=destination/archive_hash[:16]
    allowed={'adapter_config.json','adapter_model.safetensors','tokenizer_config.json',
        'tokenizer.json','chat_template.jinja','special_tokens_map.json','added_tokens.json',
        'vocab.json','merges.txt'}
    with zipfile.ZipFile(archive) as bundle:
        names=bundle.namelist()
        if len(names)!=len(set(names)) or sum(i.file_size for i in bundle.infolist())>512*1024*1024:
            raise ValueError('Invalid or oversized adapter archive')
        experiment=json.loads(bundle.read('experiment.json'))
        config=json.loads(bundle.read('adapter/adapter_config.json'))
        if (experiment.get('training_mode')!='pilot' or config.get('peft_type')!='LORA'
            or experiment.get('base_model')!='unsloth/Qwen2.5-7B-Instruct-bnb-4bit'
            or config.get('base_model_name_or_path')!=experiment['base_model']):
            raise ValueError('Expected the Qwen2.5 7B pilot LoRA archive')
        target.mkdir(parents=True,exist_ok=True)
        for name in allowed:
            member='adapter/'+name
            if member in names:
                data=bundle.read(member);path=target/name
                if path.exists() and path.read_bytes()!=data:raise ValueError('Local adapter data changed')
                if not path.exists():path.write_bytes(data)
        required={'adapter_config.json','adapter_model.safetensors','tokenizer.json','tokenizer_config.json','chat_template.jinja'}
        if not all((target/name).is_file() for name in required):raise ValueError('Incomplete adapter archive')
        template_hash=sha256(target/'chat_template.jinja')
        if template_hash!=experiment.get('chat_template_sha256'):raise ValueError('Chat template hash mismatch')
        manifest={'archive_sha256':archive_hash,'adapter_sha256':sha256(target/'adapter_model.safetensors'),
            'training_base_model':experiment['base_model'],'training_base_revision':experiment['base_revision'],
            'training_mode':'pilot','chat_template_sha256':template_hash,
            'adapter_files':{name:sha256(target/name) for name in sorted(allowed) if (target/name).is_file()}}
        (target/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return target,manifest


class MPSRuntime:
    def __init__(self,adapter,manifest,base_source):
        self.adapter=Path(adapter);self.manifest=manifest;self.base_source=base_source
        self.lock=threading.Lock();self.model=None;self.tokenizer=None

    def load(self):
        import torch
        from transformers import AutoModelForCausalLM,AutoTokenizer,QuantoConfig
        from peft import PeftModel
        if not torch.backends.mps.is_available():raise RuntimeError('MPS unavailable; run on Apple Silicon outside the filesystem sandbox')
        configure_mps_quantization()
        if self.base_source['model']!=BASE_MODEL:raise ValueError('Unexpected base model')
        for name,digest in self.manifest['adapter_files'].items():
            if sha256(self.adapter/name)!=digest:raise ValueError('Adapter file changed before loading')
        torch.set_num_threads(4)
        self.tokenizer=AutoTokenizer.from_pretrained(self.adapter,local_files_only=True)
        if hashlib.sha256(self.tokenizer.chat_template.encode()).hexdigest()!=self.manifest['chat_template_sha256']:
            raise ValueError('Loaded tokenizer template differs from training')
        base=AutoModelForCausalLM.from_pretrained(self.base_source['snapshot'],local_files_only=True,
            dtype=torch.float16,device_map='mps',low_cpu_mem_usage=True,
            quantization_config=QuantoConfig(weights='int4',modules_to_not_convert=['lm_head']),
            attn_implementation='sdpa')
        self.model=PeftModel.from_pretrained(base,self.adapter,is_trainable=False,autocast_adapter_dtype=False).eval()
        if any(p.device.type!='mps' for p in self.model.parameters()):raise RuntimeError('Model was not fully placed on MPS')
        from safetensors.torch import load_file
        saved=load_file(self.adapter/'adapter_model.safetensors')
        parameters=dict(self.model.named_parameters())
        for name,tensor in saved.items():
            loaded_name=name.replace('.lora_A.','.lora_A.default.').replace('.lora_B.','.lora_B.default.')
            parameter=parameters.get(loaded_name)
            if parameter is None or not torch.equal(parameter.detach().cpu(),tensor.to(dtype=parameter.dtype)):
                raise RuntimeError('Saved LoRA weights did not load exactly at the deployment dtype')
        loaded_lora_tensors=len(saved)
        del saved,parameters
        self.identity={'model':MODEL,'device':'mps','base_model':BASE_MODEL,
            'base_revision':self.base_source['revision'],**self.manifest,
            'loaded_lora_tensors':loaded_lora_tensors,'active_adapters':list(self.model.active_adapters),
            'runtime_source_sha256':sha256(__file__),
            'server_source_sha256':sha256(Path(__file__).resolve().parents[1]/'mps_server.py'),
            'deployment_note':'Original CUDA NF4 training base replaced by the compatible official base with Quanto int4 for MPS; not bit-identical to Colab or OpenRouter.',
            'generation':SETTINGS,'packages':{name:importlib.metadata.version(name) for name in
                ('torch','transformers','peft','optimum-quanto')}}
        torch.mps.synchronize()
        return self.identity

    def generate(self,prompt):
        """Chunk prefill to bound attention memory. Never truncate a shopper observation."""
        import torch
        if not isinstance(prompt,str) or not prompt:raise ValueError('A nonempty prompt is required')
        ids=self.tokenizer.apply_chat_template([{'role':'user','content':prompt}],
            tokenize=True,add_generation_prompt=True,return_tensors='pt')
        prompt_tokens=int(ids.shape[1])
        if ids.shape[1]+SETTINGS['max_output_tokens']>SETTINGS['max_context_tokens']:
            raise ValueError('Full observation exceeds context; no truncation or model request applied')
        # Quanto Tensor subclasses need ordinary version counters on this Torch build.
        with self.lock,torch.no_grad():
            started=perf_counter();ids=ids.to('mps');past=None;output=[]
            for offset in range(0,ids.shape[1],SETTINGS['prefill_chunk_tokens']):
                end=min(ids.shape[1],offset+SETTINGS['prefill_chunk_tokens'])
                result=self.model(input_ids=ids[:,offset:end],past_key_values=past,
                    attention_mask=torch.ones((1,end),device='mps',dtype=torch.long),
                    use_cache=True,logits_to_keep=1,return_dict=True)
                past=result.past_key_values
            eos=self.model.generation_config.eos_token_id or self.tokenizer.eos_token_id
            eos=set(eos if isinstance(eos,list) else [eos]);finish='length'
            for _ in range(SETTINGS['max_output_tokens']):
                token=int(result.logits[0,-1].argmax().item());output.append(token)
                if token in eos:finish='stop';break
                result=self.model(input_ids=torch.tensor([[token]],device='mps'),past_key_values=past,
                    use_cache=True,logits_to_keep=1,return_dict=True)
                past=result.past_key_values
            torch.mps.synchronize()
            elapsed=(perf_counter()-started)*1000
            text=self.tokenizer.decode(output,skip_special_tokens=True)
            del result,past,ids
            torch.mps.empty_cache()
        return {'raw_response':text,'finish_reason':finish,'identity':self.identity,
            'usage':{'prompt_tokens':prompt_tokens,'completion_tokens':len(output)},'inference_ms':elapsed}
