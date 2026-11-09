"""Prepare local adapter data and pin/download its compatible public MPS base."""
import argparse
import json
import os
from pathlib import Path

from agents.mps_runtime import BASE_MODEL,prepare_adapter


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adapter',type=Path,required=True)
    args=parser.parse_args()
    root=Path(__file__).resolve().parent/'models';root.mkdir(exist_ok=True)
    adapter,manifest=prepare_adapter(args.adapter,root/'adapters')
    os.environ['HF_HOME']=str(root/'huggingface')
    from huggingface_hub import HfApi,snapshot_download
    source=root/'qwen-base-source.json'
    data=json.loads(source.read_text()) if source.exists() else {
        'model':BASE_MODEL,'revision':HfApi().model_info(BASE_MODEL,token=False).sha}
    if data['model']!=BASE_MODEL:raise ValueError('Unexpected pinned base model')
    data['snapshot']=snapshot_download(BASE_MODEL,revision=data['revision'],token=False,
        allow_patterns=['*.safetensors','*.json','*.jinja','*.txt','*.model'])
    source.write_text(json.dumps(data,indent=2)+'\n')
    print(f"Prepared adapter {manifest['adapter_sha256'][:12]} at {adapter}")
    print(f"Pinned compatible base: {BASE_MODEL} @ {data['revision']}")


if __name__=='__main__':main()
