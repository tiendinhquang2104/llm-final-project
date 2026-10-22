"""Hidden task results for scoped train statements; post-inference use only."""
from src.task3.round23_contract import input_values,pack_input
from src.task3.witness_oracles import oracle as previous_task_oracle


def expected_output(family,scope,text):
    values=input_values(scope,text)
    if family=='SYN-UPPER':return values.upper()
    if family=='SYN-COUNT':return str(len(values))
    if family=='SYN-MAXDIFF':return str(sum(a-b for a,b in values))
    if family=='SYN-COUNTEVEN':return str(sum(a%2==0 for a,b in values))
    # Mathematical definitions already verified in Round22, with this round's
    # stricter lexical domain gate and explicit per-case filename projection.
    if scope['kind']=='scalar':canonical=str(values)
    elif scope['kind']=='array':canonical=str(len(values))+'\n'+' '.join(map(str,values))
    elif scope['kind']=='power':canonical=' '.join(map(str,values))
    elif scope['kind']=='csv':canonical='\n'.join(f'{a},{b}'for a,b in values)
    else:canonical=text
    return previous_task_oracle(family,pack_input(scope,canonical))
