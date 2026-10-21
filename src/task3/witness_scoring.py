"""Post-inference witness adjudication. Never used to construct model prompts."""
from __future__ import annotations
from src.task3.witness_oracles import oracle


def score_witness(family,prediction,compiler,execute):
    result={'input_valid':False,'actual_correct':None,'expected_correct':None,'distinguishes':False,'actual':None,'oracle_stdout':None}
    if not isinstance(prediction,dict)or prediction.get('status')=='uncertain':return result|{'reason':'missing_or_uncertain_prediction'}
    witness=prediction.get('input')
    try:
        # The frozen mathematical helper accepts Python Unicode digits. C++
        # submissions use LC_ALL=C, so enforce the authored ASCII input scope
        # here before either oracle evaluation or execution. Post-inference only.
        if not isinstance(witness,dict):raise ValueError('input object required')
        files=witness.get('files')
        if not isinstance(files,dict):raise ValueError('files object required')
        texts=[witness.get('stdin'),*files.keys(),*files.values()]
        if not all(isinstance(t,str) and t.isascii() and all(32<=ord(c)<127 or c in '\t\n\r\v\f' for c in t) for t in texts):raise ValueError('ASCII C-locale input required')
        expected=oracle(family,witness)
    except (ValueError,TypeError,KeyError)as exc:return result|{'reason':'invalid_input: '+str(exc)}
    result.update(input_valid=True,oracle_stdout=expected)
    if compiler['status']=='error':
        actual={'termination':'compile_error','stdout':'','executed':False,'compiler_diagnostic':compiler.get('stderr','')}
    else:
        actual=execute(witness)
        actual['termination']='ok'if actual['returncode']==0 and not actual['timeout']else 'timeout'if actual['timeout']or actual['returncode']in (-9,-24)else 'runtime_error'
    proposed=prediction.get('predicted_actual',{})
    result.update(actual=actual,actual_correct=isinstance(proposed,dict)and proposed.get('termination')==actual['termination']and isinstance(proposed.get('stdout'),str)and proposed['stdout'].strip()==actual['stdout'].strip(),
                  expected_correct=isinstance(prediction.get('predicted_expected'),str)and prediction['predicted_expected'].strip()==expected,
                  distinguishes=actual['termination']!='ok'or actual['stdout'].strip()!=expected)
    return result


def pair_metrics(rows):
    successes=sum(bool(r['base_success']and r['mutant_success'])for r in rows)
    return {'pairs':len(rows),'successes':successes,'accuracy':successes/len(rows)if rows else None}
