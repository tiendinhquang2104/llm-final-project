import pytest
from src.task3.round23_oracles import expected_output


def test_new_train_family_oracles_have_hand_checked_results():
    csv={'kind':'csv','filename':'md.csv','rows_max':6,'value_lo':-9,'value_hi':9}
    assert expected_output('SYN-MAXDIFF',csv,'2,5\n-3,1\n')=='-7'
    assert expected_output('SYN-COUNT',csv,'2,5\n-3,1\n')=='2'
    assert expected_output('SYN-COUNTEVEN',csv,'-2,5\n3,1\n0,-1\n')=='2'
    string={'kind':'string','alphabet':'aAzZ09','min_length':1,'max_length':6}
    assert expected_output('SYN-UPPER',string,'aZ09')=='AZ09'


def test_scope_is_checked_before_mathematical_oracle():
    s={'kind':'scalar','lo':0,'hi':10}
    assert expected_output('SYN-FACT',s,'5')=='120'
    assert expected_output('SYN-FACT',s,'+5')=='120'
    for text in ['11','٥','1\x1c']:
        with pytest.raises(ValueError):expected_output('SYN-FACT',s,text)
