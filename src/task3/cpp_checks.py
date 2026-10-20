"""Bounded mechanical C++11 observations, never a feedback or solution grader.

Linux x86_64 only. Both compiler and correction run after Landlock, seccomp,
no_new_privs and uid/gid dropping. An unavailable restriction fails closed.
Filesystem metadata may be visible through stat; private contents, writes outside
scratch, network syscalls and runtime process creation are denied. The compiler
can read the system toolchain and write only its own disposable scratch tree.
This is defense in depth for small synthetic checks, not a general code runner.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import errno
import json
import os
import platform
import re
import resource
import selectors
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, is_dataclass
from pathlib import Path

VERSION = "r12-bounded-cpp11-v2"
_DIGITS = 'Đọc số nguyên không âm n (0 <= n <= 10^9). In "True" nếu tổng các chữ số của n chia hết cho 3, ngược lại in "False".'
_GCD = (
    "Đọc hai số nguyên không âm a, b (0 <= a, b <= 10^9, không đồng thời bằng 0). In ra ước chung lớn nhất của a và b."
)
# Deliberately narrow statement contracts; unrelated/changed specifications are refused.
_CONTRACTS = {
    _DIGITS: (
        "digit_sum_divisible_by_3",
        [
            ("0\n", "True"),
            ("3\n", "True"),
            ("1\n", "False"),
            ("123\n", "True"),
            ("124\n", "False"),
            ("999999999\n", "True"),
            ("1000000000\n", "False"),
        ],
    ),
    _GCD: (
        "nonnegative_gcd",
        [
            ("12 18\n", "6"),
            ("0 17\n", "17"),
            ("17 0\n", "17"),
            ("1 1\n", "1"),
            ("1000000000 500000000\n", "500000000"),
            ("999999937 999999929\n", "1"),
        ],
    ),
}


def isolation_support() -> dict:
    """Probe prerequisites only; actual application is checked in every child."""
    out = {
        "available": False,
        "platform": platform.system(),
        "architecture": platform.machine(),
        "mechanisms": [
            "Landlock",
            "seccomp_allowlist",
            "no_new_privs",
            "unprivileged_uid_gid",
            "rlimits",
            "wall_timeout",
            "bounded_output",
        ],
    }
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        return out | {"reason": "only audited Linux x86_64 syscall interface is supported"}
    libc = ctypes.CDLL(None, use_errno=True)
    abi = libc.syscall(444, 0, 0, 1)
    out["landlock_abi"] = abi
    if abi < 3:
        return out | {"reason": "Landlock ABI >=3 is required (including truncate restriction)"}
    library = ctypes.util.find_library("seccomp")
    if not library:
        return out | {"reason": "libseccomp is unavailable"}
    out["seccomp_library"] = library
    return out | {"available": True, "reason": "prerequisites present; child must apply all restrictions"}


def _landlock(scratch: Path, executable: Path, phase: str, toolchain_root: Path | None = None) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    # ABI3 rights through TRUNCATE. Newer rights are not required: seccomp denies
    # ioctl and other write/metadata mutation operations in execution phase.
    handled = (1 << 15) - 1
    attr = ctypes.c_uint64(handled)
    fd = libc.syscall(444, ctypes.byref(attr), ctypes.sizeof(attr), 0)
    if fd < 0:
        raise OSError(ctypes.get_errno(), "landlock_create_ruleset")

    class Rule(ctypes.Structure):
        _pack_ = 1
        _fields_ = [("allowed_access", ctypes.c_uint64), ("parent_fd", ctypes.c_int32)]

    def allow(path: Path, access: int):
        if not path.exists():
            return
        directory = path.is_dir()
        if not directory:
            access &= (1 << 0) | (1 << 1) | (1 << 2) | (1 << 14)
        pfd = os.open(path, os.O_PATH | os.O_CLOEXEC)
        try:
            rule = Rule(access, pfd)
            if libc.syscall(445, fd, 1, ctypes.byref(rule), 0) < 0:
                raise OSError(ctypes.get_errno(), "landlock_add_rule")
        finally:
            os.close(pfd)

    try:
        read_exec = (1 << 0) | (1 << 2) | (1 << 3)
        for path in ("/usr/lib", "/lib", "/lib64"):
            allow(Path(path).resolve(), read_exec)
        allow(Path("/etc/ld.so.cache"), 1 << 2)
        if executable.parent != scratch:
            allow(executable, read_exec)
        if phase == "compile":
            if toolchain_root is not None:
                allow(toolchain_root / "usr", read_exec)
            # Debian/Ubuntu GCC helpers may live outside /usr/lib. Grant only
            # this toolchain tree, only in compile phase; runtime cannot read it.
            for path in ("/usr/bin", "/bin", "/usr/include", "/usr/local/include", "/usr/libexec/gcc"):
                allow(Path(path).resolve(), read_exec)
            # Plain files/directories only: never device/socket/symlink creation.
            writes = (1 << 1) | (1 << 4) | (1 << 5) | (1 << 7) | (1 << 8) | (1 << 14)
            allow(Path("."), read_exec | writes)
            allow(Path("/dev/null"), (1 << 1) | (1 << 2))
        else:
            allow(Path("."), read_exec)
        if libc.prctl(38, 1, 0, 0, 0) != 0:
            raise OSError(ctypes.get_errno(), "PR_SET_NO_NEW_PRIVS")
        if libc.syscall(446, fd, 0) < 0:
            raise OSError(ctypes.get_errno(), "landlock_restrict_self")
    finally:
        os.close(fd)


def _seccomp(phase: str, library: str) -> None:
    lib = ctypes.CDLL(library, use_errno=True)
    lib.seccomp_init.argtypes = [ctypes.c_uint32]
    lib.seccomp_init.restype = ctypes.c_void_p
    lib.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    lib.seccomp_rule_add.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint]
    lib.seccomp_load.argtypes = [ctypes.c_void_p]
    lib.seccomp_release.argtypes = [ctypes.c_void_p]
    # Deny by default. The library also rejects wrong architectures/x32 calls.
    ctx = lib.seccomp_init(0x00050000 | errno.EPERM)
    if not ctx:
        raise RuntimeError("seccomp_init failed")
    common = """read write readv writev close fstat newfstatat stat lstat statx lseek
        mmap mprotect munmap brk rt_sigaction rt_sigprocmask rt_sigreturn
        pread64 access faccessat faccessat2 open openat getcwd readlink readlinkat
        arch_prctl set_tid_address set_robust_list rseq prlimit64 getrlimit
        getrandom futex futex_waitv clock_gettime gettimeofday time uname sysinfo
        getpid getppid gettid getuid geteuid getgid getegid getgroups
        exit exit_group execve fcntl dup dup2 dup3 getdents64 sched_getaffinity
        sched_yield restart_syscall sigaltstack madvise mremap""".split()
    compiler = """pipe pipe2 fork vfork wait4 waitid chdir fchdir umask
        mkdir mkdirat unlink unlinkat rename renameat renameat2
        ftruncate truncate fsync fdatasync fchmod
        getrusage times getpgrp getpgid setsid setpgid""".split()
    try:
        for name in common + (compiler if phase == "compile" else []):
            number = lib.seccomp_syscall_resolve_name(name.encode())
            if number >= 0 and lib.seccomp_rule_add(ctx, 0x7FFF0000, number, 0) != 0:
                raise RuntimeError("seccomp allow rule failed: " + name)
        if phase == "compile":
            # glibc posix_spawn uses clone3 then vfork/clone. ENOSYS requests a
            # fallback; unrestricted clone3 would allow namespace manipulation.
            number = lib.seccomp_syscall_resolve_name(b"clone3")
            if number >= 0 and lib.seccomp_rule_add(ctx, 0x00050000 | errno.ENOSYS, number, 0) != 0:
                raise RuntimeError("seccomp clone3 deny failed")

            class Compare(ctypes.Structure):
                _fields_ = [
                    ("arg", ctypes.c_uint),
                    ("op", ctypes.c_uint),
                    ("datum_a", ctypes.c_uint64),
                    ("datum_b", ctypes.c_uint64),
                ]

            lib.seccomp_rule_add_array.argtypes = [
                ctypes.c_void_p,
                ctypes.c_uint32,
                ctypes.c_int,
                ctypes.c_uint,
                ctypes.POINTER(Compare),
            ]
            # Accept normal fork/vfork flags; reject namespaces, ptrace, threads.
            allowed = 0xFF | 0x100 | 0x4000 | 0x1000000 | 0x200000
            cmp = Compare(0, 7, (~allowed) & ((1 << 64) - 1), 0)  # MASKED_EQ
            number = lib.seccomp_syscall_resolve_name(b"clone")
            if lib.seccomp_rule_add_array(ctx, 0x7FFF0000, number, 1, ctypes.byref(cmp)) != 0:
                raise RuntimeError("seccomp constrained clone failed")
        if lib.seccomp_load(ctx) != 0:
            raise OSError(ctypes.get_errno(), "seccomp_load")
    finally:
        lib.seccomp_release(ctx)


def _sandbox_main(config: dict) -> None:
    """Trusted child launcher: no untrusted instruction executes before setup."""
    stage = "resolve"
    try:
        scratch = Path(config["scratch"]).resolve()
        os.chdir(scratch)
        os.umask(0o077)
        phase = config["phase"]
        executable = Path(config["command"][0]).resolve()
        seccomp_library = ctypes.util.find_library("seccomp")
        if not seccomp_library:
            raise RuntimeError("libseccomp not found")
        # Resolve privileged resources before dropping; no capabilities retained.
        if os.getuid() == 0:
            os.setgroups([])
            os.setresgid(65534, 65534, 65534)
            os.setresuid(65534, 65534, 65534)
        if os.getuid() == 0 or os.geteuid() == 0:
            raise RuntimeError("refusing root execution")
        libc = ctypes.CDLL(None, use_errno=True)
        if libc.prctl(4, 0, 0, 0, 0) != 0:  # PR_SET_DUMPABLE=0
            raise OSError(ctypes.get_errno(), "PR_SET_DUMPABLE")
        for key, value in [
            (resource.RLIMIT_CORE, 0),
            (resource.RLIMIT_NOFILE, 64),
            (resource.RLIMIT_CPU, 12 if phase == "compile" else 3),
            (resource.RLIMIT_AS, (768 if phase == "compile" else 192) * 1024 * 1024),
            (resource.RLIMIT_FSIZE, 16 * 1024 * 1024),
            (resource.RLIMIT_NPROC, 32 if phase == "compile" else 0),
        ]:
            resource.setrlimit(key, (value, value))
        stage = "landlock"
        toolchain_root = Path(config["toolchain_root"]) if config.get("toolchain_root") else None
        _landlock(scratch, executable, phase, toolchain_root)
        stage = "seccomp"
        _seccomp(phase, seccomp_library)
        stage = "exec"
        command = config["command"]
        # The scratch directory may sit below an ancestor unreadable to nobody.
        if executable.parent == scratch:
            command = ["./" + executable.name] + command[1:]
        env = {"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C", "HOME": str(scratch), "TMPDIR": str(scratch)}
        if phase == "compile" and toolchain_root is not None:
            env["PATH"] = str(toolchain_root / "usr/bin") + ":" + env["PATH"]
            env["LD_LIBRARY_PATH"] = str(toolchain_root / "usr/lib/x86_64-linux-gnu")
        os.execve("./" + executable.name if executable.parent == scratch else str(executable), command, env)
    except BaseException as error:
        os.write(2, ("ISOLATION_SETUP_FAILED: " + stage + ": " + repr(error) + "\n").encode()[:4096])
        os._exit(125)


def _run_isolated(
    command: list[str],
    *,
    scratch: Path,
    phase: str,
    input_text: str = "",
    wall_seconds: float = 2.0,
    output_bytes: int = 32768,
    extra_args: list[str] | None = None,
) -> dict:
    """Bound total captured stdout+stderr, time and all descendant lifetimes."""
    if phase not in {"compile", "execute"}:
        raise ValueError("unknown sandbox phase")
    command = [str(x) for x in command] + (extra_args or [])
    result = {
        "command": command,
        "input": input_text,
        "stdout": "",
        "stderr": "",
        "returncode": None,
        "status": "BLOCKED_ISOLATION",
        "output_truncated": False,
        "limits": {"wall_seconds": wall_seconds, "output_bytes": output_bytes},
    }
    support = isolation_support()
    result["isolation"] = support
    if not support["available"]:
        return result
    scratch = scratch.resolve()
    scratch.mkdir(parents=True, exist_ok=True)
    if os.getuid() == 0:
        os.chown(scratch, 65534, 65534)
    os.chmod(scratch, 0o700)
    config = {"command": command, "scratch": str(scratch), "phase": phase}
    portable = os.environ.get("TASK3_CPP_TOOLCHAIN_ROOT") if phase == "compile" else None
    if portable:
        root = Path(portable).resolve()
        if root == Path("/") or not (root / "usr/bin/g++").exists():
            raise ValueError("TASK3_CPP_TOOLCHAIN_ROOT must contain the dedicated public compiler usr/bin/g++")
        config["toolchain_root"] = str(root)
        result["isolation"]["portable_toolchain_root"] = str(root)
    # Isolated Python ignores user/environment site customizations; no preexec_fn
    # and no inherited secret environment/file descriptors enter the child.
    launcher = [sys.executable, "-I", "-S", str(Path(__file__).resolve()), "--sandbox-child", json.dumps(config)]
    start = time.monotonic()
    proc = subprocess.Popen(
        launcher,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
        close_fds=True,
        env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"},
    )
    try:
        proc.stdin.write(input_text.encode())
        proc.stdin.close()
        selector = selectors.DefaultSelector()
        chunks = {"stdout": bytearray(), "stderr": bytearray()}
        for name in chunks:
            stream = getattr(proc, name)
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, name)
        remaining = output_bytes
        status = "EXITED"
        while selector.get_map():
            delay = wall_seconds - (time.monotonic() - start)
            if delay <= 0:
                status = "TIMEOUT"
                break
            for key, _ in selector.select(min(delay, 0.1)):
                data = os.read(key.fd, min(8192, remaining + 1))
                if not data:
                    selector.unregister(key.fileobj)
                    continue
                chunks[key.data].extend(data[:remaining])
                remaining -= min(len(data), remaining)
                if sum(map(len, chunks.values())) >= output_bytes:
                    status = "OUTPUT_LIMIT"
                    break
            if status == "OUTPUT_LIMIT":
                break
        selector.close()
        if status == "EXITED":
            try:
                proc.wait(timeout=max(0.001, wall_seconds - (time.monotonic() - start)))
            except subprocess.TimeoutExpired:
                status = "TIMEOUT"
        # Kill even after a clean parent exit: compiler descendants must not leak.
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait(timeout=2)
        result.update(
            status=status,
            returncode=proc.returncode,
            stdout=chunks["stdout"].decode("utf-8", "replace"),
            stderr=chunks["stderr"].decode("utf-8", "replace"),
            output_truncated=status == "OUTPUT_LIMIT",
        )
        if result["stderr"].startswith("ISOLATION_SETUP_FAILED:"):
            result["status"] = "BLOCKED_ISOLATION"
    finally:
        for stream in (proc.stdout, proc.stderr):
            stream.close()
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
    result["elapsed_seconds"] = time.monotonic() - start
    return result


def _extract(feedback: str) -> tuple[str | None, str | None]:
    markers = list(re.finditer(r"^\s*(`{3,}|~{3,})([^\n]*)\n?", feedback, re.M))
    if len(markers) != 2 or markers[0].group(1) != markers[1].group(1) or markers[1].group(2).strip():
        return None, "incomplete_or_ambiguous_cpp_fence"
    if markers[0].group(2).strip().lower() not in {"cpp", "c++", "cxx", "cc"}:
        return None, "incomplete_or_ambiguous_cpp_fence"
    code = feedback[markers[0].end() : markers[1].start()]
    # Ignore literals/comments when checking delimiters. Compilation is still the
    # authority on C++ syntax; this only refuses visibly unfinished fragments.
    tokens = re.sub(
        r'R"([^ ()\\\t\r\n]{0,16})\(.*?\)\1"|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|//[^\n]*|/\*.*?\*/',
        "",
        code,
        flags=re.S,
    )
    if not re.search(r"\b(?:int|signed)\s+main\s*\(", tokens):
        return code, "not_complete_translation_unit"
    stack = []
    for char in tokens:
        if char in "({[":
            stack.append(char)
        elif char in ")}]":
            if not stack or stack.pop() != {")": "(", "}": "{", "]": "["}[char]:
                return code, "not_complete_translation_unit"
    if stack or not tokens.rstrip().endswith("}") or re.search(r"(?<!\.)\.\.\.(?!\.)", tokens):
        return code, "not_complete_translation_unit"
    return code, None


def check_correction(record, feedback: str, *, work_root: Path, case_tag: str) -> dict:
    """Measure a complete synthetic single-problem correction; never grade prose.

    Exact supported statement prose may be followed by a Markdown example table.
    A replacement function is not integrated into the student's program.
    """
    row = asdict(record) if is_dataclass(record) else dict(record)
    out = {
        "version": VERSION,
        "sample_id": row.get("sample_id"),
        "status": "NOT_VERIFIED",
        "reason": None,
        "extracted_code": None,
        "compile": None,
        "tests": [],
        "explanation_assessment": "NOT_ASSESSED",
        "limitations": [
            "Only declared small cases; no exhaustive correctness claim.",
            "Code observations do not assess the verbal explanation.",
        ],
    }
    if row.get("source") not in {"synthetic", "synthetic-heldout"}:
        return out | {"reason": "non_synthetic_source"}
    if row.get("exam_type") != "single_problem" or len(row.get("problems", [])) > 1:
        return out | {"reason": "unsupported_exam_type"}
    if any(p.get("io_mode", "stdin/stdout") != "stdin/stdout" for p in row.get("problems", [])):
        return out | {"reason": "unsupported_io_mode"}
    statement = " ".join(row.get("statement", "").split())
    examples = {
        _DIGITS: "| Input | Output | |---|---| | 123 | True | | 124 | False |",
        _GCD: "| Input | Output | |---|---| | 12 18 | 6 |",
    }
    contract = _CONTRACTS.get(statement)
    if contract is None:
        for prose, table in examples.items():
            if statement == prose + " " + table:
                contract = _CONTRACTS[prose]
                break
    if not contract:
        return out | {"reason": "unsupported_statement_contract"}
    out["contract"] = contract[0]
    code, reason = _extract(feedback)
    out["extracted_code"] = code
    if reason:
        return out | {"reason": reason}
    if len(code.encode()) > 65536:
        return out | {"reason": "correction_source_limit"}
    support = isolation_support()
    out["isolation"] = support
    if not support["available"]:
        return out | {"status": "BLOCKED_ISOLATION", "reason": support["reason"]}
    portable_root = os.environ.get("TASK3_CPP_TOOLCHAIN_ROOT")
    compiler = str(Path(portable_root).resolve() / "usr/bin/g++") if portable_root else shutil.which("g++")
    if not compiler or not Path(compiler).is_file():
        return out | {"status": "BLOCKED_COMPILER", "reason": "g++ not found in PATH"}
    work_root = Path(work_root)
    work_root.mkdir(parents=True, exist_ok=True)
    safe_tag = re.sub(r"[^A-Za-z0-9_.-]", "_", case_tag)[:80] or "case"
    evidence = Path(tempfile.mkdtemp(prefix=safe_tag + "-", dir=work_root))
    (evidence / "correction.cpp").write_text(code, encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="task3-cpp-") as dirname:
        scratch = Path(dirname)
        (scratch / "correction.cpp").write_text(code, encoding="utf-8")
        os.chmod(scratch / "correction.cpp", 0o644)
        command = [
            compiler,
            "-std=c++11",
            "-O0",
            "-Wall",
            "-Wextra",
            "-fmax-errors=8",
            "correction.cpp",
            "-o",
            "correction",
        ]
        compiled = _run_isolated(command, scratch=scratch, phase="compile", wall_seconds=20.0)
        out["compile"] = compiled
        if compiled["status"] == "BLOCKED_ISOLATION":
            out["status"] = "BLOCKED_ISOLATION"
        elif compiled["status"] != "EXITED" or compiled["returncode"] != 0:
            out["status"] = "COMPILE_FAILED" if compiled["status"] == "EXITED" else "COMPILE_" + compiled["status"]
        else:
            binary = scratch / "correction"
            if not stat.S_ISREG(binary.lstat().st_mode):
                raise RuntimeError("compiler did not create a regular correction executable")
            # Linker chmod(path) is deliberately denied by seccomp because
            # Landlock cannot restrict metadata mutation. The trusted parent
            # grants execute permission only to this checked, private output.
            os.chmod(binary, 0o500)
            for input_text, expected in contract[1]:
                run = _run_isolated(
                    [str(scratch / "correction")], scratch=scratch, phase="execute", input_text=input_text
                )
                run["expected_stdout"] = expected
                run["comparison"] = "strip_leading_and_trailing_whitespace_only"
                run["observed_match"] = (
                    run["status"] == "EXITED" and run["returncode"] == 0 and run["stdout"].strip() == expected
                )
                out["tests"].append(run)
                if run["status"] in {"BLOCKED_ISOLATION", "TIMEOUT", "OUTPUT_LIMIT"}:
                    break
            if any(x["status"] == "BLOCKED_ISOLATION" for x in out["tests"]):
                out["status"] = "BLOCKED_ISOLATION"
            elif all(x["observed_match"] for x in out["tests"]):
                out["status"] = "SMALL_CASES_MATCH"
            else:
                out["status"] = "SMALL_CASE_MISMATCH"
    out["evidence_directory"] = str(evidence)
    (evidence / "measurement.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out


if __name__ == "__main__" and len(sys.argv) == 3 and sys.argv[1] == "--sandbox-child":
    _sandbox_main(json.loads(sys.argv[2]))
