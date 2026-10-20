#!/usr/bin/env python3
"""Load the single pilot adapter, avoiding legacy PEFT wrapper introspection bug.

The original R15 backend/prompt and frozen two-stage flow remain byte-identical.
Only the adapter loader differs: precision inspects actual bitsandbytes base
layers, rather than a same-named PEFT wrapper lacking compute_dtype.
"""
import json
import os
from pathlib import Path
import sys
REPO=Path(__file__).resolve().parents[1];sys.path.insert(0,str(REPO))
from scripts.task3_round18 import ROOT,verify,sha
from scripts.task3_round18_flow import run_set
from src.task3.dataset import write_json
from src.utils.config import load_config

def main():
 verify();f=json.loads((ROOT/'two-stage-freeze.json').read_text())
 for p,h in f['implementation'].items():assert sha(REPO/p)==h,'frozen flow changed'
 os.environ.setdefault('HF_HOME',str(REPO/'outputs/task3/hf-cache'));os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
 from src.task3.inference import HFBackend
 from peft import PeftModel
 import bitsandbytes as bnb
 import torch
 cfg=load_config(REPO/'configs/task3/r18_two_stage.yaml');backend=HFBackend(cfg)
 adapter=REPO/'checkpoints/task3/r18-pilot/adapter';train=json.loads((ROOT/'training-result.json').read_text())
 assert sha(adapter/'adapter_model.safetensors')==train['adapter_tensor_sha256']
 backend.model=PeftModel.from_pretrained(backend.model,str(adapter),is_trainable=False);backend.model.eval()
 assert all(p.device.type=='cuda' for p in backend.model.parameters())
 compute=sorted({str(m.compute_dtype) for m in backend.model.modules() if isinstance(m,bnb.nn.Linear4bit)})
 assert compute==['torch.bfloat16']
 cfg['adapter']=str(adapter);backend.model.generation_config.max_time=cfg['generation_max_time_s']
 backend.precision_audit.update(adapter_tensor_sha256=train['adapter_tensor_sha256'],quantized_compute_dtypes=compute,adapter_loader_sha256=sha(__file__))
 run_set('evaluation',backend,cfg,'C');write_json(ROOT/'C/runtime.json',backend.runtime_metadata());verify()
if __name__=='__main__':main()
