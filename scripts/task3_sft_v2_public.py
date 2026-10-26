"""Prepare/freeze, run once, verify, or export the selected V2 public candidate."""
import argparse
import os
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ.update(HF_HOME='/workspace/llm-final-project/outputs/task3/hf-cache',HF_HUB_OFFLINE='1',
                  TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
from src.task3.sft_v2_public_runtime import prepare,infer,export,verify,preserve
from src.task3.sft_v1_experiment import write_json

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('phase',choices=['prepare','infer','export','verify'])
    p.add_argument('--out',default='outputs/task3/sft-v2-public-20261026-run1'); a=p.parse_args()
    repo=Path(__file__).resolve().parents[1]; out=(repo/a.out).resolve()
    if not out.is_relative_to(repo/'outputs/task3') or not out.is_dir(): raise ValueError('existing fresh run directory required')
    if a.phase=='verify':
        verify(repo,out); write_json(out/'preservation-verification.json',preserve(repo,out)); print('Verified frozen public inputs/code/checkpoint and historical artifacts.')
    else: {'prepare':prepare,'infer':infer,'export':export}[a.phase](repo,out)
