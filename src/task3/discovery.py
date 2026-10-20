"""Experimental evidence discovery. Inputs deliberately exclude labels and feedback.

This is a bounded recognizer, not a C++ semantic analyzer. A supported error does
not imply complete error coverage. Compiler success never certifies clean code.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from src.synth.taxonomy import LABEL_SPACE
from src.task3.schema import _CPP_TOKEN

SUPPORTED_GROUPS = (LABEL_SPACE[0], 'Lỗi vòng lặp', 'Lỗi hard-code', 'Lỗi logic')


@dataclass(frozen=True)
class DiscoveryInput:
    code: str
    statement: str
    problems: tuple = ()
    compiler_status: str = 'unavailable'
    compiler_diagnostic: str = ''

    def __post_init__(self):
        if not isinstance(self.code, str) or not isinstance(self.statement, str):
            raise TypeError('source and statement must be text')
        if len(self.code) > 200_000:
            raise ValueError('source exceeds discovery bound')
        if any(set(p) - {'pid','prototype'} for p in self.problems):
            raise ValueError('problem input permits only pid/prototype')


def masked(code, *, literals=True):
    """Keep offsets; erase comments and optionally string/character literals."""
    chars = list(code)
    for m in _CPP_TOKEN.finditer(code):
        token = m.group()
        if token.startswith(('//','/*')) or (literals and token.startswith(('"',"'",'R"'))):
            chars[m.start():m.end()] = ['\n' if c == '\n' else ' ' for c in token]
    return ''.join(chars)


def _span(code, start, end):
    return {'start':start, 'end':end, 'line_start':code[:start].count('\n')+1,
            'line_end':code[:end].count('\n')+1, 'quote':code[start:end]}


def _pid(item, function=None):
    if function:
        found = [p['pid'] for p in item.problems if re.search(r'\b'+re.escape(function)+r'\s*\(',p.get('prototype',''))]
        if len(found)==1:return found[0]
    return item.problems[0]['pid'] if len(item.problems)==1 else None


def _finding(item, rule, start, end, group, fact, cause, evidence, action=None, pid=None):
    return {'finding_id':hashlib.sha256(f'{rule}:{start}:{end}:{item.code}'.encode()).hexdigest()[:20],
            'problem_id':pid, 'taxonomy_group':group, 'source_span':_span(item.code,start,end),
            'observed_fact':fact, 'cause':cause, 'evidence':dict(evidence,rule=rule),
            'confidence':'direct_compiler' if rule=='compiler_error' else 'bounded_relation',
            'status':'supported_error', 'repair_action':action}


def _action(target,reference,start,end,replacement,text):
    return {'target':target,'reference':reference,'span_start':start,'span_end':end,
            'replacement':replacement,'text':text}


def discover(item: DiscoveryInput):
    """Generate candidates then verify bounded relations; record every rejection.

    Accepted findings are verified again by validate_finding before rendering.
    No model calls, gold, teacher text, test reports or provenance in this API.
    """
    findings, rejected, hypotheses = [], [], []
    def reject(rule,quote,reason):
        rejected.append({'rule':rule,'quote':quote,'reason':reason,'status':'hypothesis'})
        hypotheses.append({'rule':rule,'status':'hypothesis','reason':reason})
    lines=item.code.splitlines(keepends=True)
    seen=set()
    remapped=bool(re.search(r'^\s*#\s*(?:line\b|\d)',masked(item.code,literals=False),re.M))
    for line in item.compiler_diagnostic.splitlines():
        m=re.match(r'([^\n]+?):(\d+):(\d+):\s*(fatal error|error|warning):\s*(.*)',line)
        if not m:continue
        filename,ln,col,severity,_=m.groups();ln=int(ln)
        if severity=='warning':
            reject('compiler_warning',line,'warning is not compiler rejection');continue
        if remapped:
            reject('compiler_error',line,'preprocessor line remapping prevents physical source binding');continue
        if item.compiler_status!='compile_error' or filename not in {'<stdin>','-'} or not 1<=ln<=len(lines):
            reject('compiler_error',line,'status/path/source location not supported');continue
        if ln in seen:continue
        seen.add(ln)
        start=sum(map(len,lines[:ln-1]));end=start+len(lines[ln-1].rstrip('\r\n'))
        if start==end:
            reject('compiler_error',line,'empty source line');continue
        findings.append(_finding(item,'compiler_error',start,end,LABEL_SPACE[0],
            f'Compiler báo error tại dòng {ln}.',
            'Compiler từ chối biên dịch tại vị trí này; chưa suy ra thêm nguyên nhân ngữ nghĩa.',
            {'diagnostics':[line],'compiler_status':item.compiler_status},pid=_pid(item)))
    clean=masked(item.code)
    if re.search(r'^\s*#\s*(?:define|if|elif|else|endif|undef|line)\b',masked(item.code,literals=False),re.M):
        reject('semantic_scope','preprocessor','macros/conditional compilation require preprocessing; semantic rules disabled')
    else:
        # Function bodies must be flat: nested control flow/aliases are unsupported.
        funcs=list(re.finditer(r'\b(?:void|int|bool)\s+(\w+)\s*\(([^{}()]*)\)\s*\{([^{}]*)\}',clean))
        visible=masked(item.code,literals=False)
        for call in re.finditer(r'\b(?:\w+\s*\.\s*open\s*\(|(?:std\s*::\s*)?ifstream\s+\w+\s*\()\s*"([A-Za-z_]\w*)"\s*\)',visible):
            if clean[call.start()].isspace():
                continue  # A call-shaped substring inside a raw/string literal is data.
            parameter=call[1]
            enclosing=next((f for f in funcs if f.start(3)<=call.start()<f.end(3)),None)
            contract=f'Read the file whose path is parameter {parameter}.'
            if not enclosing or not re.fullmatch(r'\s*(?:const\s+)?(?:std\s*::\s*)?string\s*(?:&\s*)?'+re.escape(parameter)+r'\s*',enclosing[2]):
                reject('literal_parameter',call[0],'no unique matching string parameter in flat function');continue
            if item.statement.strip()!=contract:
                reject('literal_parameter',call[0],'explicit path/parameter statement contract absent');continue
            if re.search(r'\b(?:namespace|class|struct|typedef|using)\b',clean) or not re.search(r'^\s*#\s*include\s*<fstream>',clean,re.M):
                reject('literal_parameter',call[0],'global standard stream identity not established in restricted source scope');continue
            body=visible[enclosing.start(3):enclosing.end(3)]
            literal_pattern='"'+re.escape(parameter)+'"'
            constructor=r'\s*std\s*::\s*ifstream\s+\w+\s*\(\s*'+literal_pattern+r'\s*\)\s*;\s*'
            method=r'\s*std\s*::\s*ifstream\s+(\w+)\s*;\s*\1\s*\.\s*open\s*\(\s*'+literal_pattern+r'\s*\)\s*;\s*'
            if item.compiler_status!='compiled' or not (re.fullmatch(constructor,body) or re.fullmatch(method,body)):
                reject('literal_parameter',call[0],'requires compiled flat body with proven std::ifstream receiver only');continue
            literal='"'+parameter+'"';start=visible.index(literal,call.start(),call.end());end=start+len(literal)
            action=_action(literal,parameter,start,end,parameter,f'Dùng giá trị tham số {parameter} làm đường dẫn thay cho literal tại vị trí lỗi.')
            findings.append(_finding(item,'literal_parameter',call.start(),call.end(),'Lỗi hard-code',
                f'Lời gọi mở file sử dụng literal {literal}, trong khi hàm nhận tham số {parameter}.',
                f'Literal không đọc giá trị tham số {parameter} mà đề yêu cầu dùng làm đường dẫn.',
                {'statement_quote':contract,'function':enclosing[1],'parameter':parameter},action,_pid(item,enclosing[1])))
        for loop in re.finditer(r'\bwhile\s*\(\s*([A-Za-z_]\w*)\s*\)\s*\{([^{}]*)\}',clean):
            control,body=loop.groups()
            # Exactly a local integer increment; no calls, aliases, exits or UB-prone arithmetic proof.
            inc=re.fullmatch(r'\s*(\w+)\s*\+\+\s*;\s*',body)
            prefix=clean[:loop.start()]
            local=inc and re.search(r'\bunsigned\s+(?:int\s+)?'+re.escape(inc[1])+r'\s*=\s*\d+\s*;',prefix)
            # int variant is only a hypothesis: signed overflow invalidates a nontermination proof.
            if not inc or inc[1]==control or not local:
                reject('invariant_loop',item.code[loop.start():loop.end()],'requires distinct local unsigned counter and no calls/exits/aliases');continue
            # Only a flat function with value parameter and two statements is within proof scope.
            owner=re.search(r'\bvoid\s+(\w+)\s*\(\s*(?:unsigned\s+)?int\s+'+re.escape(control)+r'\s*\)\s*\{\s*unsigned\s+(?:int\s+)?'+re.escape(inc[1])+r'\s*=\s*\d+\s*;\s*$',prefix)
            if not owner:
                reject('invariant_loop',item.code[loop.start():loop.end()],'scope/dataflow outside bounded function grammar');continue
            contract=re.fullmatch(re.escape(owner[1])+r' must (?:return|terminate) for (?:every integer|any) '+re.escape(control)+r'\.',item.statement.strip())
            if not contract:
                reject('invariant_loop',item.code[loop.start():loop.end()],'termination contract with feasible nonzero integer input not established');continue
            findings.append(_finding(item,'invariant_loop',loop.start(),loop.end(),'Lỗi vòng lặp',
                f'Điều kiện lặp chỉ đọc {control}; thân lặp chỉ tăng biến unsigned {inc[1]}.',
                f'Nếu {control} khác 0, điều kiện không đổi và thân lặp không tạo tiến triển quan sát được; C++11 không bảo đảm hành vi kết thúc theo đặc tả.',
                {'statement_quote':contract[0],'condition_variable':control,'unsigned_counter':inc[1],'proof':'value parameter invariant; unsigned wrap defined; no calls/exits/observable progress; C++11 forward-progress guarantee unavailable'},pid=_pid(item,owner[1])))
    # A deliberately tiny complete specification for demonstrating verified Level 4.
    spec=re.fullmatch(r'Program exit status must be (\d{1,3})\.',item.statement.strip())
    program=re.fullmatch(r'\s*int\s+main\s*\(\s*\)\s*\{\s*return\s+((?:0|[1-9]\d{0,2}))\s*;\s*\}\s*',clean)
    certificate=None
    if spec and program and all(0<=int(x)<=125 for x in (spec[1],program[1])) and item.compiler_status=='compiled':
        required=int(spec[1]);observed=int(program[1]);certificate={'kind':'bounded_exit_status','required':required,'observed':observed}
        if required!=observed:
            start,end=program.span(1)
            action=_action(program[1],str(required),start,end,str(required),f'Đặt trạng thái trả về thành {required} theo yêu cầu đề.')
            findings.append(_finding(item,'exit_status',start,end,'Lỗi logic',
                f'Hàm main trả trạng thái {observed}; đề yêu cầu {required}.',
                'Giá trị trả về trực tiếp khác trạng thái mà đặc tả yêu cầu.',
                {'statement_quote':spec[0],'proof':'entire program matches return-constant grammar'},action,_pid(item)))
    complete=certificate is not None
    taxonomy=list(dict.fromkeys(f['taxonomy_group'] for f in findings)) if findings else ([] if complete else None)
    return {'status':'supported_error' if findings else 'verified_for_bounded_contract' if complete else 'unknown',
            'findings':findings,'hypotheses':hypotheses,'rejected_candidates':rejected,
            'taxonomy':taxonomy,'coverage_complete':complete,'certificate':certificate,
            'unknown_reason':None if complete else 'unverified semantic families remain; absence is not clean'}


def validate_finding(item, finding):
    """Quote binding alone is insufficient: rederive and compare the whole claim."""
    if finding.get('taxonomy_group') not in LABEL_SPACE or finding.get('status')!='supported_error':
        raise ValueError('unsupported finding contract')
    if finding not in discover(item)['findings']:
        raise ValueError('cause/evidence/span/action not verified by source and statement relation')
    return True
