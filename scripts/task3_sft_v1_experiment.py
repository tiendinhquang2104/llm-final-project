"""Execute/resume the single controlled local SFT v1 QLoRA experiment."""
import argparse
import fcntl
import os
from pathlib import Path
import sys

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO))
os.environ['HF_HUB_OFFLINE']='1'
os.environ['TRANSFORMERS_OFFLINE']='1'
os.environ['TOKENIZERS_PARALLELISM']='false'
os.environ['CUDA_VISIBLE_DEVICES']='0'


def main():
    from src.task3.sft_v1_experiment import run
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--resume',action='store_true',help='Skip completed work; only safe native checkpoint continuation')
    p.add_argument('--config',type=Path,default=REPO/'configs/task3/sft_v1.yaml')
    p.add_argument('--reuse-preflight',type=Path,default=REPO/'outputs/task3/task3-sft-v1-integration-20261026/preflight-final')
    p.add_argument('--request',type=Path,default=Path('/root/.codex/attachments/534a7a41-83c5-4a00-82a1-40d46eb299f9/Pasted text.txt'))
    a=p.parse_args();out=a.out.resolve();out.parent.mkdir(exist_ok=True,parents=True)
    with (out.parent/(out.name+'.lock')).open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        run(REPO,out,a.config.resolve(),a.reuse_preflight.resolve(),a.request.resolve(),a.resume)


if __name__=='__main__':
    main()
