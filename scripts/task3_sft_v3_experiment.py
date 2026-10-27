"""Bounded explicit v3 stages; no public inference or extra recipes."""
import argparse
import json
import os
from pathlib import Path
import sys
REPO=Path(__file__).resolve().parents[1];sys.path.insert(0,str(REPO))
from src.task3 import sft_v3_runtime as runtime
from src.task3.sft_v3 import BudgetJournal
from src.task3.sft_v1_experiment import write_json


def main():
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['freeze','train','dev','train-dev','final','verify'])
    ap.add_argument('--out',type=Path,required=True);ap.add_argument('--resume',action='store_true');a=ap.parse_args();out=a.out.resolve()
    if not out.is_relative_to(REPO/'outputs/task3'):raise ValueError('run output must stay in repository')
    os.environ['HF_HOME']='/workspace/llm-final-project/outputs/task3/hf-cache'
    os.environ['HF_HUB_OFFLINE']=os.environ['TRANSFORMERS_OFFLINE']='1';os.environ['TOKENIZERS_PARALLELISM']='false'
    if a.stage=='freeze':runtime.freeze(REPO,out);return
    manifest=json.loads((out/'manifest.json').read_text());journal=BudgetJournal(out/'journal.jsonl')
    journal.append(dict(type='stage_started',stage=a.stage,resume=a.resume))
    try:
        if a.stage in ('train','train-dev'):runtime.train(REPO,out,manifest,journal,a.resume)
        if a.stage in ('dev','train-dev'):runtime.dev(REPO,out,manifest,journal)
        if a.stage=='final':runtime.final(REPO,out,manifest,journal)
        if a.stage=='verify':runtime.verify(REPO,out,manifest);write_json(out/'preservation-after.json',runtime.preservation(REPO,out))
        journal.append(dict(type='stage_completed',stage=a.stage))
    except BaseException as exc:
        journal.append(dict(type='technical_failure',stage=a.stage,error=repr(exc)))
        write_json(out/'status.json',dict(status='technical_failure',stage=a.stage,error=repr(exc)))
        raise


if __name__=='__main__':main()
