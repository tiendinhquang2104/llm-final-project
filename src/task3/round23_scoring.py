"""Post-inference executable evidence; inference runner never imports this module."""
from src.task3.round23_contract import validate_input,pack_input
from src.task3.round23_runner import termination
import subprocess


def score_prediction(prediction,scope,compiler,oracle,execute):
    result={'input_valid':False,'actual_correct':None,'expected_correct':None,'distinguishes':False,'observed':None,'oracle_expected':None}
    if not isinstance(prediction,dict)or prediction.get('status')not in('defect','no_defect_in_scope'):return result|{'reason':'missing_schema_or_uncertain'}
    text=prediction.get('input_text')
    try:validate_input(scope,text)
    except(ValueError,TypeError,KeyError)as exc:return result|{'reason':'invalid_input: '+str(exc)}
    expected=oracle(text)
    result.update(input_valid=True,oracle_expected=expected,expected_correct=isinstance(prediction.get('expected'),str)and prediction['expected'].strip()==expected)
    diagnostic=compiler.get('stderr',compiler.get('diagnostic',''))
    if compiler['status']=='error'and diagnostic:actual={'termination':'compile_error','stdout':'','executed':False,'compiler_diagnostic':diagnostic}
    elif compiler['status']!='pass':return result|{'reason':'compiler unavailable or missing diagnostic'}
    else:
        try:
            actual=execute(pack_input(scope,text))
            if actual.get('executed')is not True:raise RuntimeError('execution infrastructure unavailable')
            actual['termination']=termination(actual)
        except(OSError,RuntimeError,ValueError,subprocess.SubprocessError)as exc:return result|{'reason':'execution_unavailable: '+str(exc)}
    actual_text=actual['stdout'].strip()if actual['termination']=='ok'else '<'+actual['termination']+'>'
    return result|{'input_valid':True,'actual_correct':isinstance(prediction.get('actual'),str)and prediction['actual'].strip()==actual_text,
                  'expected_correct':isinstance(prediction.get('expected'),str)and prediction['expected'].strip()==expected,
                  'distinguishes':actual['termination']!='ok'or actual['stdout'].strip()!=expected,'observed':actual,'oracle_expected':expected}


def strict_member_success(status,score,is_base,mechanism_correct,taxonomy_exact):
    return status==('no_defect_in_scope'if is_base else'defect')and mechanism_correct is True and taxonomy_exact is True and score['input_valid']and score['actual_correct']is True and score['expected_correct']is True and (not score['distinguishes']if is_base else score['distinguishes'])
