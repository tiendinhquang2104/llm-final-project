"""Precision contracts; real checkpoint behavior is checked by paired GPU runs."""
import pytest

from src.utils.config import load_config


def test_bf16_config_changes_only_quantization():
    base = load_config('configs/task3/self_diagnosis_zero_shot_round10.yaml')
    bf16 = load_config('configs/task3/self_diagnosis_zero_shot_round10_bf16.yaml')
    assert {k: (base.get(k), bf16.get(k)) for k in base.keys() | bf16.keys() if base.get(k) != bf16.get(k)} == {
        'load_in_4bit': (True, False),
    }


def test_unquantized_load_explicitly_uses_bf16_on_selected_gpu():
    torch = pytest.importorskip('torch')
    from src.task3.inference import model_load_options

    options = model_load_options({'revision': 'PINNED', 'load_in_4bit': False}, device_index=0)
    assert options == {
        'revision': 'PINNED', 'trust_remote_code': False,
        'device_map': {'': 0}, 'dtype': torch.bfloat16,
    }


def test_nf4_load_retains_existing_quantization_contract():
    torch = pytest.importorskip('torch')
    from src.task3.inference import model_load_options

    options = model_load_options({'revision': 'PINNED'}, device_index=0, bf16_supported=True)
    quant = options['quantization_config']
    assert quant.load_in_4bit is True
    assert quant.bnb_4bit_quant_type == 'nf4'
    assert quant.bnb_4bit_use_double_quant is True
    assert quant.bnb_4bit_compute_dtype == torch.bfloat16
    assert options['device_map'] == {'': 0}
    assert 'dtype' not in options  # Preserve the measured NF4 baseline's non-quantized dtype behavior.


def test_precision_check_rejects_cpu_parameters_instead_of_reporting_gpu_success():
    torch = pytest.importorskip('torch')
    from src.task3.inference import inspect_model_precision

    model = torch.nn.Linear(2, 2, dtype=torch.bfloat16)
    with pytest.raises(RuntimeError, match='CUDA'):
        inspect_model_precision(model, load_in_4bit=False)
