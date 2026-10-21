"""Confinement tests use synthetic security probes, never student datasets."""
from pathlib import Path
import pytest
from src.task3.cpp_sandbox import CppSandbox


def test_sandbox_refuses_path_escape_input(tmp_path):
    with pytest.raises(ValueError,match='basename'):
        CppSandbox.validate_files({'../escape':'x'})


def test_runtime_policy_denies_network_and_process_escape():
    assert not {'socket','connect','clone','clone3','fork','vfork','mount','ptrace','kill','chroot','setuid','setgid'}&set(CppSandbox.execution_syscalls)
    assert 'openat' in CppSandbox.execution_syscalls


def test_privileged_setup_is_mandatory(tmp_path):
    with pytest.raises((ValueError,FileNotFoundError),match='root|prepared'):
        CppSandbox(tmp_path/'missing')


def test_runtime_cannot_mutate_files_or_create_unbounded_entries():
    assert not {'mkdir','rename','unlink','ftruncate','truncate','pwrite64','chmod','fchmod'}&set(CppSandbox.execution_syscalls)


def test_timeout_process_exit_race_is_recorded_not_raised(tmp_path,monkeypatch):
    import subprocess
    import os
    class Process:
        pid=1234567
        returncode=0
        calls=0
        def wait(self,timeout=None):
            self.calls+=1
            if self.calls==1:raise subprocess.TimeoutExpired('test',2)
            return 0
    monkeypatch.setattr(subprocess,'Popen',lambda *a,**kw:Process())
    def gone(*a):raise ProcessLookupError()
    monkeypatch.setattr(os,'killpg',gone)
    s=CppSandbox.__new__(CppSandbox)
    assert s._call(tmp_path,['test'],'')['timeout']is True


@pytest.fixture(scope='module')
def prepared_sandbox(tmp_path_factory):
    import os
    root=os.environ.get('TASK3_CPP_SANDBOX_ROOT')
    if not root:pytest.skip('set TASK3_CPP_SANDBOX_ROOT for actual confinement probes')
    # Rootfs materialization uses hardlinks, so scratch must share its filesystem.
    import tempfile
    parent=Path(root).parent/'integration-test-jails';parent.mkdir(exist_ok=True)
    return CppSandbox(root),Path(tempfile.mkdtemp(prefix='test-',dir=parent))


def test_loaded_filter_denies_host_network_privilege_and_writes(prepared_sandbox):
    s,path=prepared_sandbox
    code=r'''#include <unistd.h>
#include <fcntl.h>
#include <sys/socket.h>
#include <sys/stat.h>
int main(){if(getuid()!=64022||getgroups(0,nullptr)!=0)return 1;
if(open("/workspace/llm-final-project/README.md",O_RDONLY)>=0)return 2;
if(socket(AF_INET,SOCK_STREAM,0)>=0)return 3;
if(fork()>=0)return 4;
if(setuid(0)==0||chroot("/")==0)return 5;
if(open("/work/new",O_CREAT|O_WRONLY,0600)>=0||mkdir("/work/newdir",0700)==0)return 6;
return 0;}'''
    jail,c=s.compile(code,path);assert c['status']=='pass',c
    assert s.run(jail)['returncode']==0


def test_loaded_limits_stop_cpu_and_bound_output(prepared_sandbox):
    s,path=prepared_sandbox
    jail,c=s.compile('int main(){for(;;){}}',path);assert c['status']=='pass'
    r=s.run(jail);assert r['timeout']or r['returncode']==-24
    code='#include <unistd.h>\nint main(){char a[4096]={};for(int i=0;i<1000;i++)write(1,a,sizeof a);}'
    jail,c=s.compile(code,path);assert c['status']=='pass'
    r=s.run(jail);assert r['returncode']!=0 and len(r['stdout'].encode())<=65536


def test_readonly_input_replacement_and_memory_limit(prepared_sandbox):
    s,path=prepared_sandbox
    code='#include <fstream>\n#include <iostream>\nint main(){std::ifstream f("data.csv");int x;f>>x;std::cout<<x;}'
    jail,c=s.compile(code,path);assert c['status']=='pass'
    assert s.run(jail,files={'data.csv':'41'})['stdout']=='41'
    assert s.run(jail,files={'data.csv':'42'})['stdout']=='42'
    code='#include <new>\nint main(){try{char* p=new char[1024ul*1024*1024];delete[]p;return 7;}catch(const std::bad_alloc&){return 0;}}'
    jail,c=s.compile(code,path);assert c['status']=='pass'
    assert s.run(jail)['returncode']==0
