"""Precision contracts; real checkpoint behavior is checked by paired GPU runs."""
import pytest

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


def test_precision_check_ignores_peft_linear4bit_wrapper_but_audits_bnb_layer():
    torch = pytest.importorskip('torch')
    bnb = pytest.importorskip('bitsandbytes')
    from types import SimpleNamespace
    from src.task3.inference import inspect_model_precision

    class Linear4bit:
        """PEFT's wrapper has the same class name but no compute_dtype."""

    base_layer = bnb.nn.Linear4bit(2, 2, compute_dtype=torch.bfloat16)

    class Model:
        is_loaded_in_4bit = True
        hf_device_map = {}
        config = SimpleNamespace(_commit_hash=None)

        def parameters(self):
            return [SimpleNamespace(dtype=torch.uint8, device=torch.device('cuda:0'), numel=lambda: 2)]

        def modules(self):
            return [self, Linear4bit(), base_layer]

    audit = inspect_model_precision(Model(), load_in_4bit=True)

    assert audit['quantized_compute_dtypes'] == ['torch.bfloat16']
