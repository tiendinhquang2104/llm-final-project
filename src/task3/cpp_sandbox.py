"""Linux C++ confinement using existing chroot/setuid capabilities, no namespaces.

Designed for bounded offline tests, not a general multi-user execution service.
Compiler limits are per process: <=4 processes, 512MiB and CPU soft4/hard5 seconds each,
10s wall, 8MiB per output file; no aggregate compiler disk quota. Only the fixed
trusted toolchain runs under that write-enabled profile. Generated executables
use a read-only filesystem syscall policy and <=64KiB per inherited output file.
This is not a kernel/VM boundary or a multi-tenant service.
Every child loses root/capabilities and inherits a syscall allowlist. The jail
has only trusted toolchain files and its own work directory, no proc/dev/network.
"""
from __future__ import annotations
import ctypes
import errno
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import tempfile
import time

_COMMON = '''read write readv writev close fstat newfstatat stat lstat statx lseek
mmap mprotect munmap brk mremap madvise arch_prctl access faccessat faccessat2
open openat readlink readlinkat getcwd chdir fcntl ioctl getdents64
rt_sigaction rt_sigprocmask rt_sigreturn sigaltstack futex set_tid_address
set_robust_list rseq getpid getppid gettid getuid geteuid getgid getegid getgroups
clock_gettime clock_getres gettimeofday time getrandom uname sysinfo prlimit64
getrlimit getrusage sched_getaffinity sched_yield exit exit_group execve
pread64 pwrite64 ftruncate truncate unlink unlinkat rename renameat mkdir rmdir
umask fchmod chmod fchdir dup dup2 dup3'''.split()
_COMPILER_EXTRA='vfork fork wait4 waitid pipe pipe2 rt_sigsuspend setrlimit'.split()


class CppSandbox:
    execution_syscalls=tuple(x for x in _COMMON if x not in 'ioctl pwrite64 ftruncate truncate unlink unlinkat rename renameat mkdir rmdir fchmod chmod'.split())
    uid=64022
    def __init__(self, root):
        self.root=Path(root).resolve()
        if not (self.root/'READY.json').is_file():raise FileNotFoundError('prepared sandbox root required')
        if os.geteuid()!=0:raise ValueError('root setup capabilities required; never run without confinement')
        self.sec=ctypes.CDLL('libseccomp.so.2',use_errno=True)
        self.sec.seccomp_init.argtypes=[ctypes.c_uint32];self.sec.seccomp_init.restype=ctypes.c_void_p
        self.sec.seccomp_syscall_resolve_name.argtypes=[ctypes.c_char_p];self.sec.seccomp_syscall_resolve_name.restype=ctypes.c_int
        self.sec.seccomp_rule_add.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_int,ctypes.c_uint]
        self.sec.seccomp_load.argtypes=[ctypes.c_void_p];self.sec.seccomp_release.argtypes=[ctypes.c_void_p]
        class Compare(ctypes.Structure):
            _fields_=[('arg',ctypes.c_uint),('op',ctypes.c_uint),('a',ctypes.c_uint64),('b',ctypes.c_uint64)]
        self.Compare=Compare
        self.sec.seccomp_rule_add_array.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_int,ctypes.c_uint,ctypes.POINTER(Compare)]
        self.libc=ctypes.CDLL(None,use_errno=True)
        self.libc.prctl.argtypes=[ctypes.c_int,ctypes.c_ulong,ctypes.c_ulong,ctypes.c_ulong,ctypes.c_ulong]
        self.libc.prctl.restype=ctypes.c_int

    @staticmethod
    def validate_files(files):
        if any(not isinstance(k,str)or Path(k).name!=k or k in ('.','..','')or '/'in k or '\\'in k for k in files):
            raise ValueError('input filename must be a simple basename')

    @classmethod
    def prepare(cls, root):
        root=Path(root).resolve()
        if root.exists():raise FileExistsError('sandbox root already exists; no overwrite')
        root.mkdir(parents=True)
        copied={}
        def copy(src,dest=None):
            src=Path(src);dest=root/str(dest or src).lstrip('/')
            dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(src,dest);dest.chmod(0o555 if os.access(src,os.X_OK)else 0o444)
            copied[str(dest.relative_to(root))]=hashlib.sha256(dest.read_bytes()).hexdigest()
        programs=['/usr/bin/g++','/usr/bin/as','/usr/bin/ld','/usr/bin/true','/usr/bin/id',
                  subprocess.check_output(['g++','-print-prog-name=cc1plus'],text=True).strip(),
                  subprocess.check_output(['g++','-print-prog-name=collect2'],text=True).strip()]
        for src in programs:copy(src)
        for program in programs:
            raw=subprocess.check_output(['ldd',program],text=True)
            for line in raw.splitlines():
                for word in line.split():
                    if word.startswith('/')and Path(word).is_file():copy(word)
        for folder in ['/usr/lib/gcc/x86_64-linux-gnu/13','/usr/include/c++/13','/usr/include/x86_64-linux-gnu','/usr/include/linux','/usr/include/asm-generic']:
            target=root/folder.lstrip('/');shutil.copytree(folder,target,dirs_exist_ok=True,symlinks=False)
        for p in Path('/usr/include').glob('*.h'):copy(p)
        for name in ['Scrt1.o','crti.o','crtn.o','libc.so','libc_nonshared.a','libm.so']:
            copy('/usr/lib/x86_64-linux-gnu/'+name)
        for name in ['libm.so.6','libmvec.so.1','libstdc++.so.6','libgcc_s.so.1']:
            copy('/lib/x86_64-linux-gnu/'+name)
        for p in root.rglob('*'):
            if p.is_symlink():raise ValueError('trusted root must contain no symlinks')
            if p.is_dir():p.chmod(0o555)
            elif p.is_file():p.chmod(0o555 if os.access(p,os.X_OK)else 0o444)
        (root/'READY.json').write_text(json.dumps({'compiler':subprocess.check_output(['g++','--version'],text=True).splitlines()[0],'programs':programs,'copied_hashes':copied,'policy':'chroot + drop uid/gid/groups/cap bounding set + no_new_privs + seccomp allowlist + rlimits; no proc/dev; closed fds'}))
        (root/'READY.json').chmod(0o444);root.chmod(0o555)
        return cls(root)

    def _enter(self, jail, compile_phase):
        os.setsid()
        resource.setrlimit(resource.RLIMIT_CORE,(0,0))
        resource.setrlimit(resource.RLIMIT_AS,(512<<20,512<<20))
        resource.setrlimit(resource.RLIMIT_CPU,(4,5)if compile_phase else (1,2))
        resource.setrlimit(resource.RLIMIT_NPROC,(4,4)if compile_phase else (1,1))
        resource.setrlimit(resource.RLIMIT_NOFILE,(64,64))
        resource.setrlimit(resource.RLIMIT_FSIZE,(8<<20,8<<20)if compile_phase else (65536,65536))
        os.chroot(jail);os.chdir('/work');os.umask(0o077)
        for cap in range(41):
            if self.libc.prctl(24,cap,0,0,0)!=0:raise OSError('cannot drop capability bounding set')
        os.setgroups([]);os.setgid(self.uid);os.setuid(self.uid)
        if os.getuid()!=self.uid or os.getgid()!=self.uid or os.getgroups():raise RuntimeError('UID isolation failed')
        class Header(ctypes.Structure):
            _fields_=[('version',ctypes.c_uint32),('pid',ctypes.c_int)]
        class Caps(ctypes.Structure):
            _fields_=[('effective',ctypes.c_uint32),('permitted',ctypes.c_uint32),('inheritable',ctypes.c_uint32)]
        header=Header(0x20080522,0);caps=(Caps*2)()
        if self.libc.capget(ctypes.byref(header),caps)!=0 or any(x.effective or x.permitted or x.inheritable for x in caps):raise RuntimeError('capabilities not zero')
        if self.libc.prctl(38,1,0,0,0)!=0 or self.libc.prctl(39,0,0,0,0)!=1:raise RuntimeError('no_new_privs failed')
        context=self.sec.seccomp_init(0x00050000|errno.EPERM)
        if not context:raise RuntimeError('seccomp_init failed')
        try:
            for name in (_COMMON+_COMPILER_EXTRA if compile_phase else list(self.execution_syscalls)):
                number=self.sec.seccomp_syscall_resolve_name(name.encode())
                if number<0:continue
                if not compile_phase and name in ('open','openat'):
                    mask=os.O_ACCMODE|os.O_CREAT|os.O_TRUNC|os.O_APPEND|0x400000
                    cmp=self.Compare(1 if name=='open' else 2,7,mask,0)
                    rc=self.sec.seccomp_rule_add_array(context,0x7fff0000,number,1,ctypes.byref(cmp))
                else:rc=self.sec.seccomp_rule_add(context,0x7fff0000,number,0)
                if rc!=0:raise RuntimeError('seccomp rule failed')
            if compile_phase:
                clone=self.sec.seccomp_syscall_resolve_name(b'clone')
                allowed=0xff|0x100|0x4000|0x1000000|0x200000
                cmp=self.Compare(0,7,(~allowed)&((1<<64)-1),0)
                if self.sec.seccomp_rule_add_array(context,0x7fff0000,clone,1,ctypes.byref(cmp))!=0:raise RuntimeError('constrained clone failed')
                clone3=self.sec.seccomp_syscall_resolve_name(b'clone3')
                if clone3>=0 and self.sec.seccomp_rule_add(context,0x00050000|errno.ENOSYS,clone3,0)!=0:raise RuntimeError('clone3 deny failed')
            if self.sec.seccomp_load(context)!=0:raise RuntimeError('seccomp_load failed')
        finally:self.sec.seccomp_release(context)

    def _call(self,jail,args,stdin,*,compile_phase=False):
        with tempfile.TemporaryFile()as inp,tempfile.TemporaryFile()as out,tempfile.TemporaryFile()as err:
            inp.write(stdin.encode());inp.seek(0);start=time.monotonic()
            proc=subprocess.Popen(args,stdin=inp,stdout=out,stderr=err,env={'PATH':'/usr/bin','LC_ALL':'C','HOME':'/work','TMPDIR':'/work'},close_fds=True,
                                  preexec_fn=lambda:self._enter(jail,compile_phase))
            timeout=False
            try:proc.wait(timeout=10 if compile_phase else 2)
            except subprocess.TimeoutExpired:
                timeout=True
                try:os.killpg(proc.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                proc.wait()
            # Compiler process groups may have children after an error/timeout.
            try:os.killpg(proc.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            out.seek(0);err.seek(0)
            return {'returncode':proc.returncode,'stdout':out.read(65536).decode(errors='replace'),'stderr':err.read(65536).decode(errors='replace'),
                    'timeout':timeout,'latency_s':time.monotonic()-start,'isolation':'chroot_uid_seccomp_rlimits','executed':True}

    def create(self,parent):
        parent=Path(parent);parent.mkdir(parents=True,exist_ok=True)
        jail=Path(tempfile.mkdtemp(prefix='jail-',dir=parent))
        shutil.copytree(self.root,jail,dirs_exist_ok=True,copy_function=os.link)
        work=jail/'work';work.mkdir();os.chown(work,self.uid,self.uid);work.chmod(0o700)
        return jail

    def trusted_probe(self,parent):
        jail=self.create(parent)
        return {'true':self._call(jail,['/usr/bin/true'],''),'identity':self._call(jail,['/usr/bin/id'],'')}

    def compile(self,code,parent):
        jail=self.create(parent);source=jail/'work/source.cpp';source.write_text(code);source.chmod(0o444)
        result=self._call(jail,['/usr/bin/g++','-std=c++11','-O0','-fmax-errors=3','/work/source.cpp','-o','/work/program'],'',compile_phase=True)
        binary=jail/'work/program'
        if result['returncode']==0:
            os.chown(binary,0,0);binary.chmod(0o555)
            result['binary_sha256']=hashlib.sha256(binary.read_bytes()).hexdigest()
        result['status']='pass'if result['returncode']==0 else 'error'
        return jail,result

    def run(self,jail,stdin='',files=None):
        files=files or {};self.validate_files(files)
        for name,value in files.items():
            path=Path(jail)/'work'/name
            if name in ('source.cpp','program'):raise ValueError('reserved jail basename')
            if path.exists()or path.is_symlink():
                import stat
                st=path.lstat()
                if not stat.S_ISREG(st.st_mode)or st.st_uid!=0 or st.st_nlink!=1:raise ValueError('unsafe existing jail input')
                path.unlink()
            with path.open('x')as stream:stream.write(value)
            path.chmod(0o444)
        return self._call(jail,['/work/program'],stdin)
