"""Explicit bounded stages; final commands require a persisted dev selection."""
import argparse
import json
import os
from pathlib import Path
import sys
REPO=Path(__file__).resolve().parents[1];sys.path.insert(0,str(REPO))
from src.task3.sft_v2 import BudgetJournal
from src.task3 import sft_v2_runtime as runtime


def main():
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['freeze','ar15-dev','train','final-native','ar15-final'])
    ap.add_argument('--out',type=Path,required=True);ap.add_argument('--resume',action='store_true');args=ap.parse_args()
    out=args.out.resolve();os.environ['HF_HOME']='/workspace/llm-final-project/outputs/task3/hf-cache'
    os.environ['HF_HUB_OFFLINE']=os.environ['TRANSFORMERS_OFFLINE']='1';os.environ['TOKENIZERS_PARALLELISM']='false'
    if args.stage=='freeze':runtime.freeze(REPO,out);return
    manifest=json.loads((out/'manifest.json').read_text());journal=BudgetJournal(out/'journal.jsonl')
    journal.append(dict(type='stage_started',stage=args.stage,resume=args.resume))
    if args.stage=='train':runtime.train(REPO,out,manifest,journal,args.resume)
    elif args.stage=='final-native':runtime.final_native(REPO,out,manifest,journal)
    else:runtime.ar15(REPO,out,manifest,journal,'dev' if args.stage=='ar15-dev' else 'final')
    journal.append(dict(type='stage_completed',stage=args.stage))


if __name__=='__main__':main()
