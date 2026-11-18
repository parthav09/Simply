"""CUDA (Colab) inference for a Qwen2.5-7B QLoRA adapter; no simulation state is modified.

The served model is the NF4 base + LoRA loaded in a Colab session. Each adapter
family has its own frozen model id, so v1-pilot and impulse-v2 recordings can
never be confused with each other or with the Nov 4 MPS / Nov 8 MLX deployments.
"""
import threading
from time import perf_counter

BASE_MODEL = 'Qwen/Qwen2.5-7B-Instruct'
MODEL = 'qwen2.5-7b-pilot-cuda'               # v1 recipe on offline_demo_v1
IMPULSE_MODEL = 'qwen2.5-7b-impulse-v2-cuda'  # v2 recipe on impulse_teacher_v2
MODELS = {
    MODEL: {'training_mode': 'pilot', 'dataset': 'simply_offline_synthetic_demo_v1'},
    IMPULSE_MODEL: {'training_mode': 'impulse_v2', 'dataset': 'simply_impulse_teacher_v2'},
}
SETTINGS = {'max_output_tokens': 256, 'do_sample': False, 'device': 'cuda',
    'quantization': 'bnb-nf4', 'max_context_tokens': 16384,
    'request_seed_supported': False, 'decision_mode': 'single_action'}


def pricing(model):
    return {'model': model, 'source': 'local CUDA inference (Colab)', 'as_of': '2026-11-17',
        'input_usd_per_million': 0, 'cached_usd_per_million': 0, 'output_usd_per_million': 0,
        'cost_basis': 'No per-token API charge. Colab compute units are not attributed per request.'}


PRICING = pricing(MODEL)


class CUDARuntime:
    """Greedy, one-generation-at-a-time decoding of a single user prompt."""

    def __init__(self, model, tokenizer, identity):
        if identity.get('model') not in MODELS:
            raise ValueError('Unknown CUDA serving model id')
        self.model, self.tokenizer, self.identity = model, tokenizer, identity
        self.lock = threading.Lock()
        self.stop_ids = [i for i in (tokenizer.convert_tokens_to_ids('<|im_end|>'),
            tokenizer.convert_tokens_to_ids('<|endoftext|>')) if isinstance(i, int) and i >= 0]

    def generate(self, prompt):
        import torch
        if not isinstance(prompt, str) or not prompt:
            raise ValueError('A nonempty prompt is required')
        text = self.tokenizer.apply_chat_template([{'role': 'user', 'content': prompt}],
            tokenize=False, add_generation_prompt=True)
        inputs = self.tokenizer(text, return_tensors='pt', add_special_tokens=False)
        prompt_tokens = int(inputs['input_ids'].shape[1])
        if prompt_tokens + SETTINGS['max_output_tokens'] > SETTINGS['max_context_tokens']:
            raise ValueError('Full observation exceeds context; no truncation or model request applied')
        with self.lock, torch.inference_mode():
            inputs = inputs.to(self.model.device)
            torch.cuda.synchronize()
            started = perf_counter()
            output = self.model.generate(**inputs, max_new_tokens=SETTINGS['max_output_tokens'],
                do_sample=False, temperature=None, top_p=None, top_k=None, use_cache=True,
                # Qwen's generation_config sets repetition_penalty=1.05, applied even when greedy;
                # the MPS/MLX deployments use plain argmax, so disable it for a like-for-like model.
                repetition_penalty=1.0,
                pad_token_id=self.tokenizer.pad_token_id, eos_token_id=self.stop_ids)
            torch.cuda.synchronize()
            elapsed = (perf_counter() - started) * 1000
            generated = output[0, prompt_tokens:].tolist()
        finish = 'stop' if generated and generated[-1] in self.stop_ids else 'length'
        return {'raw_response': self.tokenizer.decode(generated, skip_special_tokens=True).strip(),
            'finish_reason': finish, 'identity': self.identity,
            'usage': {'prompt_tokens': prompt_tokens, 'completion_tokens': len(generated)},
            'inference_ms': elapsed}
