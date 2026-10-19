"""Artificial corrections; no student submissions and no semantic feedback grading."""

import hashlib
import importlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

try:
    checks = importlib.import_module("src.task3.cpp_checks")
except ModuleNotFoundError:
    checks = None

DIGITS = 'Đọc số nguyên không âm n (0 <= n <= 10^9). In "True" nếu tổng các chữ số của n chia hết cho 3,\nngược lại in "False".'
GCD = (
    "Đọc hai số nguyên không âm a, b (0 <= a, b <= 10^9, không đồng thời bằng 0).\nIn ra ước chung lớn nhất của a và b."
)
GOOD = "#include <iostream>\nint main(){long long a,b;std::cin>>a>>b;while(b){long long t=a%b;a=b;b=t;}std::cout<<a;}"


def test_bounded_checker_api_is_available():
    assert checks is not None, "bounded correction-check utility is not implemented"


@pytest.fixture
def api():
    if checks is None:
        pytest.skip("API absent; direct missing-API assertion captures RED")
    return checks


def record(**kw):
    return dict(
        source="synthetic-heldout",
        sample_id="TEST-ONLY",
        exam_type="single_problem",
        statement=GCD,
        problems=[{"pid": "P1", "io_mode": "stdin/stdout"}],
        **kw,
    )


def fence(code):
    return "Hướng dẫn sửa.\n```cpp\n" + code + "\n```"


def compiler_or_skip(api):
    portable = os.environ.get("TASK3_CPP_TOOLCHAIN_ROOT")
    if not (portable and (Path(portable) / "usr/bin/g++").exists()) and not shutil.which("g++"):
        pytest.skip("C++ compiler g++ is unavailable; no compile/run claimed")
    support = api.isolation_support()
    if not support["available"]:
        pytest.skip("Required isolation unavailable: " + support["reason"])


@pytest.mark.parametrize(
    "change,feedback,reason",
    [
        ({"source": "real"}, fence(GOOD), "non_synthetic_source"),
        ({"exam_type": "multi_problem"}, fence(GOOD), "unsupported_exam_type"),
        ({"statement": "Print any common divisor of a and b."}, fence(GOOD), "unsupported_statement_contract"),
        ({}, "```cpp\n" + GOOD, "incomplete_or_ambiguous_cpp_fence"),
        ({}, fence("int f(){return 1;}"), "not_complete_translation_unit"),
        ({}, fence("int main(){"), "not_complete_translation_unit"),
        ({}, fence(GOOD) + "\n" + fence(GOOD), "incomplete_or_ambiguous_cpp_fence"),
    ],
)
def test_refuses_unsupported_or_incomplete_without_execution(api, tmp_path, change, feedback, reason):
    r = record()
    r.update(change)
    result = api.check_correction(r, feedback, work_root=tmp_path, case_tag="refusal")
    assert result["status"] == "NOT_VERIFIED"
    assert result["reason"] == reason
    assert result["tests"] == []
    assert result["compile"] is None
    assert result["explanation_assessment"] == "NOT_ASSESSED"


def test_fails_closed_when_isolation_is_unavailable(api, tmp_path, monkeypatch):
    monkeypatch.setattr(api, "isolation_support", lambda: {"available": False, "reason": "test denial"})
    result = api.check_correction(record(), fence(GOOD), work_root=tmp_path, case_tag="blocked")
    assert result["status"] == "BLOCKED_ISOLATION"
    assert result["compile"] is None
    assert result["tests"] == []
    assert result["extracted_code"] == GOOD + "\n"


def test_actual_cpp11_gcd_inputs_outputs_are_recorded(api, tmp_path):
    compiler_or_skip(api)
    result = api.check_correction(record(), fence(GOOD), work_root=tmp_path, case_tag="gcd")
    assert result["status"] == "SMALL_CASES_MATCH"
    assert "-std=c++11" in result["compile"]["command"]
    cases = {r["input"]: r for r in result["tests"]}
    assert cases["0 17\n"]["stdout"].strip() == "17"
    assert cases["17 0\n"]["stdout"].strip() == "17"
    assert cases["12 18\n"]["expected_stdout"] == "6"
    assert cases["12 18\n"]["observed_match"] is True
    assert result["explanation_assessment"] == "NOT_ASSESSED"
    assert "semantic_grade" not in result


def test_cpp11_missing_climits_is_a_useful_compiler_failure(api, tmp_path):
    compiler_or_skip(api)
    code = "#include <iostream>\nint main(){std::cout << INT_MIN;}"
    result = api.check_correction(record(), fence(code), work_root=tmp_path, case_tag="climits")
    assert result["status"] == "COMPILE_FAILED"
    assert "INT_MIN" in result["compile"]["stderr"]
    assert result["tests"] == []


def test_actual_digits_contract_and_wrong_output_remain_measurements(api, tmp_path):
    compiler_or_skip(api)
    r = record()
    r["statement"] = DIGITS
    code = '#include <iostream>\nint main(){long long n;std::cin>>n;std::cout<<(n%3==0?"True":"False");}'
    good = api.check_correction(r, fence(code), work_root=tmp_path, case_tag="digits")
    assert good["status"] == "SMALL_CASES_MATCH"
    cases = {x["input"]: x for x in good["tests"]}
    assert cases["0\n"]["expected_stdout"] == "True"
    assert cases["1000000000\n"]["expected_stdout"] == "False"
    bad = api.check_correction(
        r, fence('#include <iostream>\nint main(){std::cout<<"True";}'), work_root=tmp_path, case_tag="wrong"
    )
    assert bad["status"] == "SMALL_CASE_MISMATCH"
    assert any(not x["observed_match"] for x in bad["tests"])


def isolated_python(api, tmp_path, program, **kw):
    support = api.isolation_support()
    if not support["available"]:
        pytest.skip("Runtime isolation unavailable: " + support["reason"])
    return api._run_isolated([sys.executable, "-I", "-S", "-c", program], scratch=tmp_path, phase="execute", **kw)


def test_sandbox_drops_root_and_denies_private_reads_network_and_fork(api, tmp_path):
    program = """import os,socket,json
out={'uid':os.getuid(), 'groups':os.getgroups()}
for name,fn in [('read',lambda:open('/etc/passwd').read()),('socket',lambda:socket.socket()),('fork',os.fork)]:
 try: fn();out[name]='ALLOWED'
 except OSError as e:out[name]=e.errno
print(json.dumps(out))"""
    run = isolated_python(api, tmp_path, program)
    assert run["status"] == "EXITED", run
    assert run["returncode"] == 0, run
    out = json.loads(run["stdout"])
    assert out["uid"] != 0
    assert out["groups"] == [] if os.getuid() == 0 else isinstance(out["groups"], list)
    assert out["read"] in {1, 13}
    assert out["socket"] == 1
    assert out["fork"] == 1


def test_sandbox_cannot_write_outside_its_scratch(api, tmp_path):
    import tempfile

    # Directly below /tmp with mode666: ordinary DAC would allow nobody to write.
    with tempfile.NamedTemporaryFile(mode="w+", prefix="test-only-world-writable-") as outside:
        outside.write("preserve")
        outside.flush()
        os.chmod(outside.name, 0o666)
        run = isolated_python(
            api,
            tmp_path / "scratch",
            'import sys\ntry:open(sys.argv[1],"w").write("changed")\nexcept OSError:print("DENIED")',
            extra_args=[outside.name],
        )
        assert run["returncode"] == 0, run
        assert run["stdout"].strip() == "DENIED"
        assert Path(outside.name).read_text() == "preserve"


def test_wall_timeout_and_output_capture_limit_are_enforced(api, tmp_path):
    timeout = isolated_python(api, tmp_path, "while True: pass", wall_seconds=0.15)
    assert timeout["status"] == "TIMEOUT"
    output = isolated_python(api, tmp_path, 'import os\nwhile True:os.write(1,b"X"*8192)', output_bytes=4096)
    assert output["status"] == "OUTPUT_LIMIT"
    assert len(output["stdout"].encode()) <= 4096
    assert output["output_truncated"] is True


def test_archive_and_runs_cli_writes_new_audit_and_preserves_inputs(api, tmp_path):
    import zipfile

    archive = tmp_path / "old.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("input_evidence/synthetic-heldout.jsonl", json.dumps({"record": record()}))
        z.writestr(
            "runs/OLD__synthetic-heldout/predictions.json",
            json.dumps([{"sample_id": "TEST-ONLY", "output": {"feedback": "No correction."}}]),
        )
    runs = tmp_path / "runs" / "NEW__synthetic-heldout"
    runs.mkdir(parents=True)
    predictions = runs / "predictions.json"
    predictions.write_text(json.dumps([{"sample_id": "TEST-ONLY", "output": {"feedback": "No correction."}}]))
    trace = runs / "predictions.traces.json"
    trace.write_text(
        json.dumps(
            [
                {
                    "sample_id": "TEST-ONLY",
                    "attempts": [
                        {"stage": "final_feedback", "raw_text": "Raw correction attempt.", "model_generated": True},
                        {"stage": "structured_plan", "raw_text": '{"findings":[]}'},
                    ],
                }
            ]
        )
    )
    before = predictions.read_bytes()
    out = tmp_path / "audit"
    script = Path(__file__).resolve().parents[1] / "scripts/task3_r7_cpp_audit.py"
    run = subprocess.run(
        [sys.executable, str(script), "--archive", str(archive), "--runs-root", str(runs.parent), "--output", str(out)],
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0, run.stderr
    rows = [json.loads(x) for x in (out / "checks.jsonl").read_text().splitlines()]
    assert {r["run_id"] for r in rows} == {"OLD__synthetic-heldout", "NEW__synthetic-heldout"}
    assert all(r["check"]["status"] == "NOT_VERIFIED" for r in rows)
    raw = [r for r in rows if r["kind"] == "raw_attempt"]
    assert len(raw) == 1
    assert raw[0]["artifact"] == str(trace)
    assert raw[0]["artifact_sha256"] == hashlib.sha256(trace.read_bytes()).hexdigest()
    assert predictions.read_bytes() == before
    repeat = subprocess.run(
        [sys.executable, str(script), "--archive", str(archive), "--output", str(out)], capture_output=True, text=True
    )
    assert repeat.returncode != 0


def test_changed_instructions_after_examples_are_not_silently_ignored(api, tmp_path):
    r = record()
    r["statement"] = GCD + "\n\n| Input | Output |\n|---|---|\n| 12 18 | 6 |\nInstead print the least common multiple."
    result = api.check_correction(r, fence(GOOD), work_root=tmp_path, case_tag="changed-contract")
    assert result["status"] == "NOT_VERIFIED"
    assert result["reason"] == "unsupported_statement_contract"
    assert result["compile"] is None


def test_compiler_cannot_include_world_readable_private_file(api, tmp_path):
    compiler_or_skip(api)
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", prefix="test-only-private-", suffix=".h") as private:
        private.write("const int TEST_SECRET = 41;\n")
        private.flush()
        os.chmod(private.name, 0o644)
        code = '#include "' + private.name + '"\nint main(){return TEST_SECRET;}'
        result = api.check_correction(record(), fence(code), work_root=tmp_path, case_tag="denied-include")
        assert result["status"] == "COMPILE_FAILED"
        assert "Permission denied" in result["compile"]["stderr"]
        assert result["tests"] == []


def test_cpp_infinite_loop_and_output_flood_are_stopped(api, tmp_path):
    compiler_or_skip(api)
    loop = api.check_correction(record(), fence("int main(){while(true){}}"), work_root=tmp_path, case_tag="loop")
    assert loop["tests"][0]["status"] == "TIMEOUT"
    flood = api.check_correction(
        record(),
        fence('#include <iostream>\nint main(){while(true)std::cout<<"xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx";}'),
        work_root=tmp_path,
        case_tag="flood",
    )
    assert flood["tests"][0]["status"] == "OUTPUT_LIMIT"
    assert len(flood["tests"][0]["stdout"].encode()) <= 32768


def test_configured_portable_compiler_does_not_require_global_path(api, tmp_path, monkeypatch):
    root = os.environ.get("TASK3_CPP_TOOLCHAIN_ROOT")
    if not root or not (Path(root) / "usr/bin/g++").exists():
        pytest.skip("No explicitly configured portable toolchain")
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    result = api.check_correction(record(), fence(GOOD), work_root=tmp_path, case_tag="portable-only")
    assert result["status"] == "SMALL_CASES_MATCH"
    assert result["compile"]["command"][0] == str(Path(root) / "usr/bin/g++")
