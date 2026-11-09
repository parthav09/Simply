"""Convert the saved PEFT pilot adapter to MLX-LM format without retraining."""
import argparse
import json
from pathlib import Path
import re

from agents.mps_runtime import prepare_adapter, sha256


def convert(archive, destination):
    import mlx.core as mx

    source, manifest = prepare_adapter(archive, destination.parent / 'adapters')
    config = json.loads((source / 'adapter_config.json').read_text())
    if (config['r'] != 16 or config['lora_alpha'] != 32 or config['lora_dropout'] != 0
            or config.get('use_rslora') or config.get('use_dora') or config.get('rank_pattern')
            or config.get('alpha_pattern') or config.get('modules_to_save')):
        raise ValueError('Unsupported pilot adapter configuration')
    weights = mx.load(str(source / 'adapter_model.safetensors'))
    converted = {}
    pattern = re.compile(r'base_model\.model\.(model\.layers\.\d+\.(?:self_attn|mlp)\.[a-z_]+)\.lora_([AB])\.weight')
    for name, tensor in weights.items():
        match = pattern.fullmatch(name)
        if not match or tensor.ndim != 2:
            raise ValueError(f'Unsupported adapter tensor: {name}')
        converted[f'{match[1]}.lora_{match[2].lower()}'] = tensor.T
    if len(converted) != 392:
        raise ValueError('Unexpected number of pilot adapter tensors')
    destination.mkdir(parents=True, exist_ok=True)
    mlx_config = {'fine_tune_type': 'lora', 'num_layers': 28,
        'lora_parameters': {'rank': 16, 'scale': 2.0, 'dropout': 0.0,
            'keys': ['self_attn.q_proj', 'self_attn.k_proj', 'self_attn.v_proj',
                'self_attn.o_proj', 'mlp.gate_proj', 'mlp.up_proj', 'mlp.down_proj']}}
    mx.save_safetensors(str(destination / 'adapters.safetensors'), converted)
    (destination / 'adapter_config.json').write_text(json.dumps(mlx_config, indent=2) + '\n')
    restored = mx.load(str(destination / 'adapters.safetensors'))
    if set(restored) != set(converted) or any(not mx.array_equal(restored[k], v).item() for k, v in converted.items()):
        raise RuntimeError('Converted adapter did not round-trip exactly')
    manifest['mlx_adapter_sha256'] = sha256(destination / 'adapters.safetensors')
    manifest['mlx_adapter_config_sha256'] = sha256(destination / 'adapter_config.json')
    (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adapter', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=Path(__file__).parent / 'models/mlx-pilot-adapter')
    args = parser.parse_args()
    result = convert(args.adapter, args.output)
    print(f"Converted and verified {392} tensors; adapter {result['adapter_sha256'][:12]}")
