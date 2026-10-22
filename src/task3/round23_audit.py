"""Deterministic post-hoc views of every old attempt, never a response repair."""
from copy import deepcopy
from src.task3.round23_contract import source_spans,json_object


def normalize_old_attempt(text,code,*,stdin_only):
    value=deepcopy(json_object(text));edits=[]
    witness=value.get('input')
    if stdin_only and isinstance(witness,dict)and isinstance(witness.get('stdin'),str)and 'files'not in witness:
        witness['files']={};edits.append('stdin_empty_files')
    quote=value.get('quote');spans=source_spans(code,quote)
    if isinstance(quote,str)and quote not in code and spans:
        value['quote']=spans[0]['source'];edits.append('source_whitespace')
    return value,edits


def independent_flags(score,role):
    valid=score['input_valid']
    unavailable=not valid and score.get('reason','').startswith(('missing_or_uncertain','raw JSON unavailable'))
    return {'input_unavailable':unavailable,'out_of_domain':not valid and not unavailable,'valid_but_nondistinguishing':bool(valid and role=='mutant'and not score['distinguishes']),
            'actual_wrong':bool(valid and score['actual_correct']is False),'expected_wrong':bool(valid and score['expected_correct']is False)}
