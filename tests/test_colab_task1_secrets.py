"""Task 1 notebook can obtain keys when Colab Secrets is unavailable."""

import json
import os
import re
import sys
import types
from pathlib import Path
from unittest import mock


def _secret_cell() -> str:
    path = Path(__file__).resolve().parents[1] / "colab" / "02_task1_baseline_api.ipynb"
    notebook = json.loads(path.read_text(encoding="utf-8"))
    return next("".join(cell["source"]) for cell in notebook["cells"]
                if cell["cell_type"] == "code" and any("def load_api_key" in line for line in cell["source"]))


def test_timeout_falls_back_to_hidden_input_once():
    class TimeoutException(Exception):
        pass

    userdata = types.SimpleNamespace(get=mock.Mock(side_effect=TimeoutException()))
    colab = types.ModuleType("google.colab")
    colab.userdata = userdata
    google = types.ModuleType("google")
    google.colab = colab
    source = re.sub(r"^PROVIDERS = .*", "PROVIDERS = ('gemini', 'openai')", _secret_cell(), flags=re.M)
    source = source.replace("RUN_LIVE = False", "RUN_LIVE = True")
    with mock.patch.dict(sys.modules, {"google": google, "google.colab": colab}), \
            mock.patch.dict(os.environ, {"GEMINI_API_KEY": "", "OPENAI_API_KEY": ""}), \
            mock.patch("getpass.getpass", side_effect=["test-gemini", "test-openai"]) as hidden:
        exec(compile(source, "secret-cell", "exec"), {"os": os})
        assert os.environ["GEMINI_API_KEY"] == "test-gemini"
        assert os.environ["OPENAI_API_KEY"] == "test-openai"
    assert userdata.get.call_count == 1
    assert hidden.call_count == 2


def test_selected_provider_only_requires_its_key():
    source = re.sub(r"^PROVIDERS = .*", "PROVIDERS = ('openai',)", _secret_cell(), flags=re.M)
    source = source.replace("RUN_LIVE = False", "RUN_LIVE = True")
    with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test-openai", "GEMINI_API_KEY": ""}), \
            mock.patch("getpass.getpass") as hidden:
        exec(compile(source, "secret-cell", "exec"), {"os": os})
    hidden.assert_not_called()
