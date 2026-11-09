"""Apple MLX inference for the saved pilot; no simulation state is modified."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import threading
from time import perf_counter

from agents.mps_runtime import BASE_MODEL, sha256

MODEL = 'qwen2.5-7b-pilot-mlx'
SETTINGS = {'max_output_tokens': 256, 'do_sample': False, 'device': 'mlx-metal',
    'quantization': 'mlx-affine-int4-group64', 'max_context_tokens': 16384,
    'prefill_chunk_tokens': 256, 'request_seed_supported': False, 'decision_mode': 'single_action'}
PRICING = {'model': MODEL, 'source': 'local MLX inference', 'as_of': '2026-11-08',
    'input_usd_per_million': 0, 'cached_usd_per_million': 0, 'output_usd_per_million': 0,
    'cost_basis': 'No per-token API charge. Local hardware, electricity and compute costs are unmeasured.'}


class MLXRuntime:
    def __init__(self, base, adapter, original, base_source):
        self.base, self.adapter, self.original = map(Path, (base, adapter, original))
        self.base_source = base_source
        self.lock = threading.Lock()

    def load(self):
        import mlx.core as mx
        from mlx.utils import tree_flatten
        from mlx_lm import load
        from mlx_lm.utils import load_tokenizer

        if not mx.metal.is_available() or mx.default_device() != mx.gpu:
            raise RuntimeError('MLX Metal GPU unavailable')
        manifest = json.loads((self.adapter / 'manifest.json').read_text())
        if self.base_source['model'] != BASE_MODEL:
            raise ValueError('Unexpected base model')
        for name, digest in manifest['adapter_files'].items():
            if sha256(self.original / name) != digest:
                raise ValueError('Original adapter file changed')
        for name, key in [('adapters.safetensors', 'mlx_adapter_sha256'), ('adapter_config.json', 'mlx_adapter_config_sha256')]:
            if sha256(self.adapter / name) != manifest[key]:
                raise ValueError('Converted adapter changed')
        config = json.loads((self.base / 'config.json').read_text())
        if config.get('quantization') != {'group_size': 64, 'bits': 4, 'mode': 'affine'}:
            raise ValueError('Unexpected MLX quantization')
        self.model, _ = load(str(self.base), adapter_path=str(self.adapter))
        self.tokenizer = load_tokenizer(self.original)
        if hashlib.sha256(self.tokenizer.chat_template.encode()).hexdigest() != manifest['chat_template_sha256']:
            raise ValueError('Loaded tokenizer template differs from training')
        saved = mx.load(str(self.adapter / 'adapters.safetensors'))
        loaded = dict(tree_flatten(self.model.parameters()))
        expected = {k for k in loaded if k.endswith(('.lora_a', '.lora_b'))}
        if set(saved) != expected or any(not mx.array_equal(value, loaded[name]).item() for name, value in saved.items()):
            raise RuntimeError('MLX adapter tensors did not load exactly')
        self.identity = {'model': MODEL, 'device': 'mlx-metal', 'base_model': BASE_MODEL,
            'base_revision': self.base_source['revision'], **manifest, 'loaded_lora_tensors': len(saved),
            'base_weights_sha256': sha256(self.base / 'model.safetensors'),
            'base_config_sha256': sha256(self.base / 'config.json'),
            'runtime_source_sha256': sha256(__file__), 'generation': SETTINGS,
            'deployment_note': 'MLX affine int4 official base; distinct from CUDA NF4 training and Quanto MPS.',
            'packages': {name: importlib.metadata.version(name) for name in ('mlx', 'mlx-lm', 'transformers')}}
        return self.identity

    def generate(self, prompt):
        from mlx_lm import stream_generate
        from mlx_lm.sample_utils import make_sampler
        if not isinstance(prompt, str) or not prompt:
            raise ValueError('A nonempty prompt is required')
        tokens = self.tokenizer.apply_chat_template([{'role': 'user', 'content': prompt}],
            tokenize=True, add_generation_prompt=True)
        if len(tokens) + SETTINGS['max_output_tokens'] > SETTINGS['max_context_tokens']:
            raise ValueError('Full observation exceeds context')
        with self.lock:
            started = perf_counter(); pieces = []; last = None
            for last in stream_generate(self.model, self.tokenizer, tokens, max_tokens=SETTINGS['max_output_tokens'],
                    sampler=make_sampler(temp=0.0), prefill_step_size=SETTINGS['prefill_chunk_tokens']):
                pieces.append(last.text)
            if last is None:
                raise RuntimeError('MLX returned no generation')
            return {'raw_response': ''.join(pieces), 'finish_reason': last.finish_reason, 'identity': self.identity,
                'usage': {'prompt_tokens': len(tokens), 'completion_tokens': last.generation_tokens},
                'inference_ms': (perf_counter() - started) * 1000}
