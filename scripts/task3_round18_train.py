#!/usr/bin/env python3
"""Exactly one final-checkpoint QLoRA pilot on frozen reviewed two-task targets."""
import json
import os
from pathlib import Path
import sys
import time
REPO=Path(__file__).resolve().parents[1];sys.path.insert(0,str(REPO))
from scripts.task3_round18 import ROOT,verify,sha
from src.task3.dataset import write_json
from src.task3.round14_runner import digest
from src.task3.inference import load_tokenizer
from src.task3.train import encode_completion,CompletionCollator
from src.utils.config import load_config

def main():
 verify();cfg=load_config(REPO/'configs/task3/r18_pilot.yaml');out=REPO/cfg['output_dir']
 if out.exists():raise ValueError('pilot output exists; no second pilot or silent restart')
 manifest=json.loads((ROOT/'targets-manifest.json').read_text());assert manifest['target_file_sha256']==sha(ROOT/'targets.private.json')
 from src.task3.two_stage_data import require_historical_isolation
 require_historical_isolation(manifest['provenance'],REPO)
 os.environ.setdefault('HF_HOME',str(REPO/'outputs/task3/hf-cache'));os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
 tokenizer=load_tokenizer(cfg);targets=json.loads((ROOT/'targets.private.json').read_text());rows=[encode_completion(tokenizer,r['messages'],r['completion'],cfg['max_seq_length']) for r in targets]
 audit={'examples':len(rows),'max_tokens':max(len(r['input_ids']) for r in rows),'supervised_tokens':sum(sum(x!=-100 for x in r['labels']) for r in rows),'truncated':False,'prompt_masked':all(r['labels'][0]==-100 for r in rows)}
 binding={'config':cfg,'config_sha256':digest(cfg),'target_sha256':manifest['target_file_sha256'],'data_manifest_sha256':sha(ROOT/'targets-manifest.json'),'evaluation_freeze_sha256':sha(ROOT/'freeze.json'),'token_audit':audit,'checkpoint_policy':'one epoch, final adapter only; no checkpoint or prompt/hparam selection from evaluation','status':'locked_before_model_load','script_sha256':sha(__file__)}
 write_json(ROOT/'training-manifest.json',binding)
 import torch
 from transformers import AutoModelForCausalLM,BitsAndBytesConfig,Trainer,TrainingArguments,TrainerCallback,set_seed
 from peft import LoraConfig,get_peft_model,prepare_model_for_kbit_training
 assert torch.cuda.device_count()==1 and torch.cuda.is_bf16_supported()
 set_seed(cfg['seed']);free,total=torch.cuda.mem_get_info();assert free>24*1024**3,'GPU still occupied or insufficient free VRAM'
 torch.cuda.reset_peak_memory_stats();started=time.perf_counter()
 quant=BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_quant_type='nf4',bnb_4bit_use_double_quant=True,bnb_4bit_compute_dtype=torch.bfloat16)
 base=AutoModelForCausalLM.from_pretrained(cfg['model_id'],revision=cfg['revision'],trust_remote_code=False,quantization_config=quant,device_map={'':0},torch_dtype=torch.bfloat16)
 assert base.config._commit_hash==cfg['revision'];base.config.use_cache=False
 base=prepare_model_for_kbit_training(base,use_gradient_checkpointing=True)
 model=get_peft_model(base,LoraConfig(r=cfg['lora_r'],lora_alpha=cfg['lora_alpha'],lora_dropout=cfg['lora_dropout'],target_modules=cfg['target_modules'],bias='none',task_type='CAUSAL_LM'))
 assert all('lora_' in n for n,p in model.named_parameters() if p.requires_grad)
 initial={n:p.detach().clone() for n,p in model.named_parameters() if 'lora_B' in n and p.requires_grad}
 class Audit(TrainerCallback):
  finite=False
  def on_pre_optimizer_step(self,args,state,control,**kwargs):
   grads=[p.grad for n,p in model.named_parameters() if p.requires_grad and p.grad is not None]
   assert grads and all(bool(torch.isfinite(g).all()) for g in grads),'nonfinite gradients'
   self.finite=self.finite or any(bool(torch.count_nonzero(g)) for g in grads)
 audit_callback=Audit()
 args=TrainingArguments(output_dir=str(out),seed=42,data_seed=42,learning_rate=cfg['learning_rate'],num_train_epochs=cfg['epochs'],per_device_train_batch_size=1,gradient_accumulation_steps=cfg['gradient_accumulation_steps'],gradient_checkpointing=True,gradient_checkpointing_kwargs={'use_reentrant':False},bf16=True,fp16=False,lr_scheduler_type=cfg['lr_scheduler_type'],warmup_ratio=cfg['warmup_ratio'],eval_strategy='no',save_strategy='no',logging_steps=1,report_to=[],push_to_hub=False)
 trainer=Trainer(model=model,args=args,train_dataset=rows,data_collator=CompletionCollator(tokenizer.pad_token_id),processing_class=tokenizer,callbacks=[audit_callback])
 write_json(out/'started.json',binding)
 try:
  trained=trainer.train()
  changed=any(bool(torch.count_nonzero(p.detach()-initial[n])) for n,p in model.named_parameters() if n in initial)
  assert changed and audit_callback.finite,'LoRA update/gradient not verified'
  trainer.save_model(str(out/'adapter'));tokenizer.save_pretrained(out/'adapter')
  hashes={p.name:sha(p) for p in (out/'adapter').glob('*') if p.is_file()}
  result={**binding,'status':'complete','optimizer_steps':trainer.state.global_step,'metrics':trained.metrics,'history':trainer.state.log_history,'gradient_finite_nonzero':audit_callback.finite,'lora_update_nonzero':changed,'checkpoint_sha256':hashes,'adapter_tensor_sha256':hashes['adapter_model.safetensors'],'gpu':torch.cuda.get_device_name(0),'free_vram_start':free,'total_vram':total,'peak_allocated':torch.cuda.max_memory_allocated(),'peak_reserved':torch.cuda.max_memory_reserved(),'wall_s':time.perf_counter()-started}
 except Exception as exc:
  write_json(out/'run.json',{**binding,'status':'failed','error':repr(exc),'step':trainer.state.global_step});raise
 write_json(out/'run.json',result);write_json(ROOT/'training-result.json',result);print(json.dumps({k:result[k] for k in ('status','optimizer_steps','adapter_tensor_sha256','peak_reserved','wall_s')}),flush=True);verify()
if __name__=='__main__':main()
