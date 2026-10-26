import copy
import math
import random
from pathlib import Path

import pytest
import yaml

from src.task3 import sft_v1_experiment as exp


def config():
    return yaml.safe_load((Path(__file__).parents[1] / 'configs/task3/sft_v1.yaml').read_text())


def test_settings_map_exact_recipe_and_reject_ignored_options(tmp_path):
    c = config()
    values = exp.training_arguments(c, tmp_path)
    assert values['num_train_epochs'] == 1
    assert values['gradient_accumulation_steps'] == 4
    assert values['save_steps'] == 80
    assert values['bf16'] and not values['fp16']
    assert values['remove_unused_columns'] is False
    assert values['gradient_checkpointing_kwargs'] == {'use_reentrant': False}
    c['training']['packing'] = True
    with pytest.raises(ValueError, match='packing'):
        exp.training_arguments(c, tmp_path)
    c = config(); c['training']['unmapped_setting'] = True
    with pytest.raises(ValueError, match='unmapped_setting'):
        exp.training_arguments(c, tmp_path)


def test_checkpoint_selection_is_loss_only_earliest_tie_and_not_promotion():
    got = exp.select_checkpoint(1., {80: 2., 160: 2.})
    assert got['step'] == 80
    assert got['improves_base_dev_loss'] is False
    assert exp.select_checkpoint(3., {80: 2., 160: 1.})['step'] == 160
    with pytest.raises(ValueError):
        exp.select_checkpoint(1., {80: math.nan, 160: 2.})


def test_resume_recovers_interrupted_checkpoint_evaluation_before_selection():
    assert exp.pending_checkpoint_evaluations(80, set()) == [80]
    assert exp.pending_checkpoint_evaluations(160, {80}) == [160]
    assert exp.pending_checkpoint_evaluations(160, set()) == [80, 160]
    assert exp.pending_checkpoint_evaluations(160, {80, 160}) == []


def test_generation_journal_never_reserves_the_same_target_twice(tmp_path):
    journal = exp.Journal(tmp_path / 'journal.jsonl')
    journal.reserve('base-dev/A', budget=2)
    with pytest.raises(ValueError, match='already reserved'):
        journal.reserve('base-dev/A', budget=2)
    journal.reserve('base-dev/B', budget=2)
    with pytest.raises(ValueError, match='budget'):
        journal.reserve('base-dev/C', budget=2)
    reloaded = exp.Journal(tmp_path / 'journal.jsonl')
    assert reloaded.reserved() == {'base-dev/A', 'base-dev/B'}


def test_evaluation_restores_all_rng_streams():
    import numpy as np
    import torch
    random.seed(17); np.random.seed(17); torch.manual_seed(17)
    before = exp.capture_rng()
    with exp.preserve_rng():
        random.random(); np.random.rand(); torch.rand(10)
    after = exp.capture_rng()
    assert before['python'] == after['python']
    assert np.array_equal(before['numpy'][1], after['numpy'][1])
    assert torch.equal(before['torch'], after['torch'])


def test_smoke_selection_has_16_distinct_train_targets_all_levels_and_clean_fault():
    examples = [dict(example_id=f'{s}-L{level}', sample_id=s, level=level,
                     completion='{"taxonomy_error":' + ('[]' if s[0] == 'C' else '["Lỗi logic"]')
                     + ',"feedback":"Phản hồi."}')
                for s in ['C1', 'C2', 'C3', 'F1', 'F2', 'F3'] for level in range(1, 5)]
    selected = exp.smoke_ids(examples)
    assert len(selected) == len(set(selected)) == 16
    assert selected == exp.smoke_ids(examples)
    assert {v.split('-L')[1] for v in selected} == {'1', '2', '3', '4'}
    assert sum(v.startswith('C') for v in selected) == 8


def test_trainer_accumulation_averages_examples_not_tokens(tmp_path):
    import torch
    from types import SimpleNamespace
    from transformers import TrainingArguments, TrainerCallback
    from src.task3.sft_v1 import make_trainer

    class Model(torch.nn.Module):
        def __init__(self):
            super().__init__(); self.weight = torch.nn.Parameter(torch.tensor(.3))
        def forward(self, input_ids, attention_mask, use_cache=False):
            shape = (*input_ids.shape,)
            return SimpleNamespace(logits=torch.stack((self.weight.expand(shape), torch.zeros(shape)), -1))

    rows = [dict(example_id=str(i), input_ids=[0] * (i + 3), attention_mask=[1] * (i + 3),
                 labels=[-100, -100] + [i % 2] * (i + 1), loss_weight=1.) for i in range(4)]
    model = Model()
    args = TrainingArguments(output_dir=str(tmp_path), use_cpu=True, report_to=[],
        per_device_train_batch_size=1, gradient_accumulation_steps=4, num_train_epochs=1,
        remove_unused_columns=False, save_strategy='no', max_grad_norm=0, disable_tqdm=True)
    trainer = make_trainer(model, args, rows, rows, 0)
    grads = []
    class Audit(TrainerCallback):
        def on_pre_optimizer_step(self, args, state, control, **kw):
            grads.append(float(model.weight.grad))
    trainer.add_callback(Audit())
    trainer.train()
    assert trainer.state.global_step == 1
    assert grads == pytest.approx([1 / (1 + math.exp(-.3)) - .5], abs=1e-6)
