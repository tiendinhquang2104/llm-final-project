#!/usr/bin/env python3
"""Run the second frozen prompt alternative; original selection remains immutable."""
from pathlib import Path
import argparse,json,os,sys,time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.task3_paired_review import W,verify,read,put
from src.task3.eval_snapshot import sha_file
from src.utils.config import load_config


def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--split',choices=['development','validation'],required=True);args=ap.parse_args()
 m=verify();f=read(W/'candidate2-freeze.private.json')
 for path,h in f['files_sha256'].items():
  if sha_file(ROOT/path)!=h:raise ValueError('candidate2 frozen code drift')
 if f['selection_sha256']!=sha_file(W/'selection.private.json'):raise ValueError('candidate2 selection drift')
 out=W/'C2'/args.split
 if (out/'started.json').exists():raise ValueError('refuse overwrite/replay')
 os.environ['HF_HOME']=str(ROOT/'outputs/task3/hf-cache');os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
 from scripts.task3_direct_sft_infer import record,Capture
 from scripts.task3_pilot_infer import load_backend
 from src.task3.round15_runner import run_records
 from src.task3.dataset import write_json
 from src.task3.submission import validate_submission
 from src.synth.feedback import FEEDBACK_LEVELS
 from src.task3.paired_level_prompt import adapter
 cfg=load_config(ROOT/m['config']['baseline']);cfg['max_time']=cfg['generation_max_time_s']
 ids={s['sample_id']for s in m['selected']if s['split']==args.split};rows=[r for r in read(W/'model-inputs.private.json')if r['sample_id']in ids];records=[record(r)for r in rows]
 out.mkdir(parents=True,exist_ok=True);put(out/'started.json',dict(arm='C2',split=args.split,config=cfg,adapter=None,selection_sha256=sha_file(W/'selection.private.json'),candidate_freeze_sha256=sha_file(W/'candidate2-freeze.private.json'),start_unix=time.time()))
 backend=load_backend(cfg);write_json(out/'runtime-before.json',backend.runtime_metadata());start=time.perf_counter()
 with adapter():result=run_records(records,Capture(backend,out,records),cfg,out,examples=())
 status=dict(requested=len(records),completed=len(result['predictions']),errors=result['errors'],elapsed_s=time.perf_counter()-start,config=cfg,runtime=backend.runtime_metadata(),schema=None)
 if not result['errors']:status['schema']=validate_submission(out/'predictions.json',{r['request_id']:FEEDBACK_LEVELS[r['requested_level']-1]for r in rows})
 write_json(out/'run.json',status);verify();print(json.dumps(dict(arm='C2',split=args.split,completed=status['completed'],requested=status['requested'],elapsed_s=status['elapsed_s'])))
if __name__=='__main__':main()
