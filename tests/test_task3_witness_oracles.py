import pytest
from src.task3.witness_oracles import oracle


def test_array_count_and_positive_domain_are_checked():
    assert oracle('SYN-SUMEVEN',{'stdin':'3\n-2 3 4\n','files':{}})=='2'
    with pytest.raises(ValueError):oracle('SYN-SUMEVEN',{'stdin':'3\n1 2','files':{}})
    with pytest.raises(ValueError):oracle('SYN-GCDARR',{'stdin':'1\n0','files':{}})


def test_csv_has_explicit_oracle_without_student_execution():
    w={'stdin':'','files':{'data.csv':'2,3\n-1,4\n'}}
    assert oracle('SYN-PROD',w)=='2'
    assert oracle('SYN-SUMPAIR',w)=='8'
    with pytest.raises(ValueError):oracle('SYN-PROD',{'stdin':'','files':{'data.csv':'2 3'}})
    with pytest.raises(ValueError):oracle('SYN-PROD',{'stdin':'','files':{'../data.csv':'2,3'}})


def test_boundary_oracles_use_task_definitions():
    def w(x):return {'stdin':str(x),'files':{}}
    assert oracle('SYN-FACT',w(0))=='1'
    assert oracle('SYN-FIB',w(0))=='0'
    assert oracle('SYN-BASE2',w(0))=='0'
    assert oracle('SYN-PRIME',w(1))=='False'
    assert oracle('SYN-ARM',w(1634))=='True'
    assert oracle('SYN-PALIN',w(100))=='False'


def test_undefined_power_case_is_excluded_from_explicit_domain():
    with pytest.raises(ValueError):oracle('SYN-POWER',{'stdin':'0 0','files':{}})
