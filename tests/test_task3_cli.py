"""Exercise real entry points using artificial records and isolated local outputs only."""

import hashlib
import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

import pytest
import yaml

from src.task3.cli import run_main, train_main
from src.task3.dataset import fixed_splits, read_json, write_json
from src.task3.schema import MODEL_ID
from tests.test_task3_dataset import record

ROOT = Path(__file__).resolve().parents[1]


def fixture_prepared(tmp_path):
    data = tmp_path / "processed"
    data.mkdir()
    rows = {
        "public": [
            record("TEST-ONLY-PUBLIC-2", source="public", split="public"),
            record("TEST-ONLY-PUBLIC-1", source="public", split="public"),
        ],
        "real-train": [record("TEST-ONLY-TRAIN", source="real", split="real-train", group_key="train")],
        "real-val": [record("TEST-ONLY-VAL", source="real", split="real-val", group_key="val")],
        "synthetic-train": [],
        "synthetic-heldout": [],
    }
    for split, records in rows.items():
        (data / f"{split}.jsonl").write_text(
            "".join(json.dumps({"record": asdict(r)}, ensure_ascii=False) + "\n" for r in records), encoding="utf-8"
        )
    _, split_metadata = fixed_splits(ROOT)
    write_json(
        data / "manifest.json",
        {
            "dataset_version": "task3-v1",
            "filter_synthetic": "strict",
            "fixed_splits": split_metadata,
            "processed_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in data.glob("*.jsonl")},
        },
    )
    config = tmp_path / "test.yaml"
    config.write_text(
        yaml.safe_dump(
            {
                "data_dir": str(data),
                "output_dir": str(tmp_path / "checkpoint"),
                "model_id": MODEL_ID,
                "revision": "c03e6d358207e414f1eca0bb1891e29f1db0e242",
                "seed": 42,
                "experiment": "real",
            }
        ),
        encoding="utf-8",
    )
    return data, config


@pytest.mark.parametrize(
    "script",
    ["task3_prepare", "run_task3", "train_task3", "evaluate_task3", "task3_gpu_preflight"],
)
def test_help_without_model_download(script):
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / f"{script}.py"), "--help"], capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "usage:" in result.stdout
    assert "Downloading" not in result.stdout


def test_public_missing_taxonomy_fails_before_model_or_data(capsys):
    with pytest.raises(SystemExit) as exc:
        run_main(["--split", "public", "--taxonomy-source", "task2-json", "--dry-run"])
    assert exc.value.code == 2
    assert "--taxonomy-json is required" in capsys.readouterr().err


def test_public_cli_mock_export_shape_and_separate_filename(tmp_path, monkeypatch, capsys):
    data, config = fixture_prepared(tmp_path)
    taxonomy = tmp_path / "TEST-ONLY.taxonomy.mock.json"
    write_json(taxonomy, {"TEST-ONLY-PUBLIC-1": [], "TEST-ONLY-PUBLIC-2": ["Lỗi logic"]})

    def forbid(*args, **kwargs):
        raise AssertionError("dry-run must never instantiate the model backend")

    monkeypatch.setattr("src.task3.cli.HFBackend", forbid)
    output = tmp_path / "predictions.json"
    run_main(
        [
            "--config",
            str(config),
            "--split",
            "public",
            "--taxonomy-source",
            "task2-json",
            "--taxonomy-json",
            str(taxonomy),
            "--allow-unverified-task2-export",
            "--output",
            str(output),
            "--dry-run",
        ]
    )
    assert not output.exists()
    prediction = read_json(tmp_path / "predictions.mock.json")
    assert [r["sample_id"] for r in prediction] == ["TEST-ONLY-PUBLIC-2", "TEST-ONLY-PUBLIC-1"]
    assert prediction[1]["output"]["taxonomy_error"] == []
    metrics = read_json(tmp_path / "predictions.mock.metrics.json")
    assert metrics["test_only_mock"] is True
    assert "TEST-ONLY MOCK" in capsys.readouterr().out


def test_dry_training_never_loads_tokenizer_or_claims_success(tmp_path, monkeypatch, capsys):
    _, config = fixture_prepared(tmp_path)

    def forbid(*args, **kwargs):
        raise AssertionError("dry-run must not load the real tokenizer")

    monkeypatch.setattr("src.task3.train.load_tokenizer", forbid)
    train_main(["--config", str(config), "--dry-run"])
    result = read_json(tmp_path / "checkpoint/dry-run.json")
    assert result["training_succeeded"] is False
    assert result["mask_smoke_test"]
    assert "NOT RUN" in capsys.readouterr().out


def test_staged_dry_run_is_safe_through_script_entrypoint(tmp_path):
    from dataclasses import asdict

    data, config_path = fixture_prepared(tmp_path)
    synthetic = record(
        "TEST-ONLY-SYNTH", source="synthetic", split="synthetic-train", group_key="synthetic"
    )
    synthetic_path = data / "synthetic-train.jsonl"
    synthetic_path.write_text(json.dumps({"record": asdict(synthetic)}) + "\n", encoding="utf-8")

    manifest = read_json(data / "manifest.json")
    manifest["processed_sha256"][synthetic_path.name] = hashlib.sha256(synthetic_path.read_bytes()).hexdigest()
    write_json(data / "manifest.json", manifest)

    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config.update(
        experiment="staged",
        stage1_fraction=0.75,
        output_dir=str(tmp_path / "staged-checkpoint"),
    )
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "train_task3.py"),
            "--config",
            str(config_path),
            "--max-steps",
            "100",
            "--dry-run",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.returncode == 0, result.stderr
    assert not (tmp_path / "staged-checkpoint/stage-synthetic").exists()
    assert not (tmp_path / "staged-checkpoint/stage-real").exists()
    assert not (tmp_path / "staged-checkpoint/stage-real").exists()


def test_manifest_tampering_rejected_before_generation(tmp_path):
    data, config = fixture_prepared(tmp_path)
    (data / "real-val.jsonl").write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="manifest"):
        run_main(["--config", str(config), "--dry-run"])
