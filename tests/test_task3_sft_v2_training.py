"""CPU-only schedule and restart-integrity contracts for the bounded v2 run."""
import json
from pathlib import Path

import pytest
import yaml

from src.task3 import sft_v2_training as v2
from src.task3.sft_v1 import sha256
from src.task3.sft_v1_experiment import Journal, training_arguments


def config():
    return yaml.safe_load((Path(__file__).parents[1] / 'configs/task3/sft_v1.yaml').read_text())


def rows():
    return [dict(example_id=f'S{s}-L{level}',sample_id=f'S{s}',level=level,loss_weight=1.)
            for s in range(240) for level in range(1,5)]


def checkpoint(directory, journal, step=120):
    directory.mkdir()
    (directory/'started.json').write_text('{}')
    (directory/'initial-adapter-identity.json').write_text('{}')
    path=directory/f'checkpoint-{step}';path.mkdir()
    for name in v2.CHECKPOINT_FILES:
        (path/name).write_text(json.dumps(dict(global_step=step)) if name=='trainer_state.json' else name)
    (path/'checkpoint-identity.json').write_text(json.dumps({name:sha256(path/name) for name in v2.CHECKPOINT_FILES}))
    for n in range(1,step+1):
        journal.append(dict(type='optimizer_intent',kind='main',step=n))
        journal.append(dict(type='optimizer_completed',kind='main',step=n))
    return path


def test_only_save_interval_differs_from_validated_v1_recipe(tmp_path):
    old=training_arguments(config(),tmp_path)
    new=v2.main_training_arguments(config(),tmp_path)
    assert {k:(old[k],new[k]) for k in old if old[k]!=new[k]}=={'save_steps':(80,120)}
    assert old.keys()==new.keys()
    bad=config();bad['training']['learning_rate']=1e-4
    with pytest.raises(ValueError,match='learning_rate'):
        v2.main_training_arguments(bad,tmp_path)


def test_960_targets_must_cover_240_sources_once_at_each_level():
    v2.validate_rows(rows())
    with pytest.raises(ValueError,match='960'):
        v2.validate_rows(rows()[:-1])
    duplicate=rows();duplicate[-1]=duplicate[0]
    with pytest.raises(ValueError,match='unique'):
        v2.validate_rows(duplicate)
    missing=rows();missing[-1]={**missing[-1],'level':3}
    with pytest.raises(ValueError,match='four Levels'):
        v2.validate_rows(missing)
    weighted=rows();weighted[0]['loss_weight']=2
    with pytest.raises(ValueError,match='weight'):
        v2.validate_rows(weighted)


def test_fresh_run_refuses_existing_outputs_without_overwriting(tmp_path):
    directory=tmp_path/'main';directory.mkdir();sentinel=directory/'started.json';sentinel.write_text('keep')
    with pytest.raises(ValueError,match='already contains'):
        v2.validate_start(directory,None,Journal(tmp_path/'journal.jsonl'))
    assert sentinel.read_text()=='keep'


def test_resume_checks_checkpoint_identity_and_exact_journal_progress(tmp_path):
    journal=Journal(tmp_path/'journal.jsonl');directory=tmp_path/'main'
    path=checkpoint(directory,journal)
    assert v2.validate_start(directory,path,journal)==120
    journal.append(dict(type='optimizer_intent',kind='main',step=121))
    with pytest.raises(ValueError,match='beyond checkpoint|progress'):
        v2.validate_start(directory,path,journal)


def test_resume_rejects_modified_state_even_when_step_is_unchanged(tmp_path):
    journal=Journal(tmp_path/'journal.jsonl');directory=tmp_path/'main'
    path=checkpoint(directory,journal)
    (path/'optimizer.pt').write_text('modified')
    with pytest.raises(ValueError,match='identity'):
        v2.validate_start(directory,path,journal)


def test_resume_rejects_missing_completed_steps_and_foreign_checkpoint(tmp_path):
    journal=Journal(tmp_path/'journal.jsonl');directory=tmp_path/'main'
    path=checkpoint(directory,journal)
    empty=Journal(tmp_path/'empty.jsonl')
    with pytest.raises(ValueError,match='progress'):
        v2.validate_start(directory,path,empty)
    other=tmp_path/'elsewhere';other.mkdir()
    with pytest.raises(ValueError,match='inside'):
        v2.validate_start(directory,other,journal)


def test_audited_trajectory_keeps_one_peak_scope_through_both_evaluations(tmp_path,monkeypatch):
    """Exercise callbacks, metadata guard, 960 exposures and step counters on CPU."""
    from contextlib import nullcontext
    from types import SimpleNamespace
    import torch
    import transformers
    from scripts import task3_sft_v1_prepare as preparation

    peak={'allocated':10,'reserved':20,'resets':0}
    def reset():
        peak['resets']+=1;peak['allocated']=10;peak['reserved']=20
    monkeypatch.setattr(torch.cuda,'reset_peak_memory_stats',reset)
    monkeypatch.setattr(torch.cuda,'synchronize',lambda:None)
    monkeypatch.setattr(torch.cuda,'max_memory_allocated',lambda:peak['allocated'])
    monkeypatch.setattr(torch.cuda,'max_memory_reserved',lambda:peak['reserved'])
    monkeypatch.setattr(v2,'preserve_rng',nullcontext)
    monkeypatch.setattr(v2,'verify_frozen',lambda *a:None)
    monkeypatch.setattr(preparation,'audit_batch',lambda *a:0)
    class Arguments(SimpleNamespace):
        def __init__(self,**kwargs):super().__init__(skip_memory_metrics=True,world_size=1,**kwargs)
        def to_dict(self):return vars(self)
    monkeypatch.setattr(transformers,'TrainingArguments',Arguments)
    class Model(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.base=torch.nn.Parameter(torch.tensor(1.),requires_grad=False)
            self.lora_B=torch.nn.Parameter(torch.tensor(.1))
            self.peft_config={'default':SimpleNamespace(to_dict=lambda:{'r':16})}
        def forward(self,input_ids,attention_mask,use_cache=False):return self.lora_B.square()
    model=Model()
    monkeypatch.setattr(v2,'adapter_identity',lambda m:{'lora_B':float(m.lora_B.detach())})
    class Trainer:
        model_accepts_loss_kwargs=False
        def __init__(self,model,args,data):
            self.model=model;self.args=args;self.data=data;self.callbacks=[]
            self.state=SimpleNamespace(global_step=0,max_steps=240)
            self.optimizer=SimpleNamespace(param_groups=[{'lr':2e-5}],state={model.lora_B:{'step':0}})
            self.lr_scheduler=SimpleNamespace(last_epoch=0)
        def get_train_dataloader(self):return [{'example_id':[r['example_id']]} for r in self.data]
        def data_collator(self,rs):return {'example_id':[r['example_id'] for r in rs]}
        def compute_loss(self,m,inputs,return_outputs=False,num_items_in_batch=None):
            return m(input_ids=torch.tensor([[0]]),attention_mask=torch.tensor([[1]]),use_cache=False)
        def add_callback(self,cb):self.callbacks.append(cb)
        def train(self,resume_from_checkpoint=None):
            assert resume_from_checkpoint is None
            cb=self.callbacks[0];cb.on_train_begin(self.args,self.state,None)
            for i,batch in enumerate(self.get_train_dataloader(),1):
                self.compute_loss(self.model,batch).backward()
                if i%4:continue
                cb.on_pre_optimizer_step(self.args,self.state,None)
                self.state.global_step+=1
                self.optimizer.state[model.lora_B]['step']=self.state.global_step
                self.lr_scheduler.last_epoch=self.state.global_step
                with torch.no_grad():model.lora_B.add_(.001)
                model.lora_B.grad=None
                cb.on_step_end(self.args,self.state,None)
                if self.state.global_step in (120,240):
                    p=Path(self.args.output_dir)/f'checkpoint-{self.state.global_step}';p.mkdir()
                    for name in v2.CHECKPOINT_FILES:
                        (p/name).write_text(json.dumps({'global_step':self.state.global_step}) if name=='trainer_state.json' else name)
                    cb.on_save(self.args,self.state,None)
            return SimpleNamespace(metrics={'train_loss':.1})
    monkeypatch.setattr(v2,'make_trainer',lambda m,args,train,dev,pad:Trainer(m,args,train))
    data=[{**r,'input_ids':[0,1]} for r in rows()]
    evaluated=[]
    def evaluate(m,step):
        evaluated.append(step);peak['allocated']=step*10;peak['reserved']=step*20
    _,result=v2.audited_train(tmp_path,tmp_path,model,SimpleNamespace(pad_token_id=0),data,[],
        [{'example_id':r['example_id']} for r in data],{'config':config()},Journal(tmp_path/'journal.jsonl'),
        checkpoint_eval=evaluate)
    assert evaluated==[120,240]
    assert result['actual_train_forward_calls']==960
    assert result['actual_optimizer_steps']==result['actual_scheduler_steps']==240
    assert peak['resets']==1
    assert result['peak_allocated_bytes']==2400
    assert result['peak_reserved_bytes']==4800
    assert 'including nested checkpoint evaluation' in result['peak_memory_scope']
