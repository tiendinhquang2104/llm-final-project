"""Short diagnosis contract and input-domain validation; no task oracle import."""
from __future__ import annotations
import json
import re
from src.task3.schema import validate_taxonomy

# Maximal-munch operators and literal prefixes matter: removing whitespace from
# a + + b or from L "text" must never manufacture a different source expression.
_LEX=re.compile(r'(?:u8|u|U|L)?R"([^ ()\\\t\r\n]{0,16})\(.*?\)\1"(?:[A-Za-z_]\w*)?|(?:u8|u|U|L)?"(?:\\.|[^"\\])*"(?:[A-Za-z_]\w*)?|(?:u|U|L)?\'(?:\\.|[^\'\\])*\'(?:[A-Za-z_]\w*)?|//[^\n]*|/\*.*?\*/|[A-Za-z_]\w*|(?:0[xX][0-9A-Fa-f]+|(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)[A-Za-z_0-9]*|>>=|<<=|->\*|\.\.\.|::|\+\+|--|->|<<|>>|<=|>=|==|!=|&&|\|\||\+=|-=|\*=|/=|%=|&=|\|=|\^=|##|\.\*|\S',re.S)


def source_spans(code,quote):
    if not isinstance(quote,str)or not quote.strip():return []
    tokens=lambda s:[m for m in _LEX.finditer(s)if not m.group().startswith(('//','/*'))]
    source=tokens(code);query=[m.group()for m in tokens(quote)]
    if not query:return []
    result=[]
    for i in range(len(source)-len(query)+1):
        if [m.group()for m in source[i:i+len(query)]]==query:
            a,b=source[i].start(),source[i+len(query)-1].end()
            result.append({'start':a,'end':b,'line':code.count('\n',0,a)+1,'source':code[a:b]})
    return result


def input_values(scope,text):
    if not isinstance(text,str)or len(text)>8192 or not text.isascii()or any(not(32<=ord(c)<127 or c in '\t\n\r\v\f')for c in text):raise ValueError('bounded ASCII C-locale input required')
    kind=scope['kind']
    if kind=='csv':
        if re.search(r'\r(?!\n)',text)or '\v'in text or '\f'in text:raise ValueError('CSV records require LF or CRLF')
        rows=text.replace('\r\n','\n').split('\n')
        if rows[-1]=='':rows.pop()
        if not 1<=len(rows)<=scope['rows_max']:raise ValueError('CSV row count outside scope')
        values=[]
        for line in rows:
            if not re.fullmatch(r'[ \t]*[+-]?[0-9]+[ \t]*,[ \t]*[+-]?[0-9]+[ \t]*',line):raise ValueError('CSV a,b row required')
            pair=tuple(map(int,line.split(',')))
            if any(not scope['value_lo']<=n<=scope['value_hi']for n in pair):raise ValueError('CSV value outside scope')
            values.append(pair)
        return values
    items=text.split()
    if kind=='string':
        if len(items)!=1 or not scope['min_length']<=len(items[0])<=scope['max_length']or any(c not in scope['alphabet']for c in items[0]):raise ValueError('string outside scope')
        return items[0]
    if not items or any(not re.fullmatch('[+-]?[0-9]+',t)for t in items):raise ValueError('integer input required')
    numbers=list(map(int,items))
    if kind=='scalar':
        if len(numbers)!=1 or not scope['lo']<=numbers[0]<=scope['hi']:raise ValueError('scalar outside scope')
        return numbers[0]
    if kind=='array':
        n,*values=numbers
        if not scope['min_items']<=n<=scope['max_items']or n!=len(values)or any(not scope['value_lo']<=x<=scope['value_hi']for x in values):raise ValueError('array outside scope')
        if scope.get('unique')and len(set(values))!=len(values):raise ValueError('array requires distinct values')
        return values
    if kind=='power':
        if len(numbers)!=2 or not(0<=numbers[0]<=3 and 0<=numbers[1]<=6)or numbers==[0,0]:raise ValueError('power outside scope')
        return numbers
    raise ValueError('unknown input scope')


def validate_input(scope,text):input_values(scope,text)


def pack_input(scope,text):
    return {'stdin':'','files':{scope['filename']:text}}if scope['kind']=='csv'else{'stdin':text,'files':{}}


def json_object(text):
    def unique_pairs(pairs):
        value={}
        for key,item in pairs:
            if key in value:raise ValueError('duplicate JSON key')
            value[key]=item
        return value
    if not isinstance(text,str):raise ValueError('JSON text required')
    body=text.strip()
    while body.startswith('<think>'):
        end=body.find('</think>')
        if end<0:raise ValueError('unterminated outer thinking block')
        body=body[end+len('</think>'):].strip()
    if body.startswith('```'):
        match=re.fullmatch(r'```(?:json)?\s*([\s\S]*?)\s*```',body)
        if match:body=match[1]
    try:value=json.loads(body,object_pairs_hook=unique_pairs)
    except(json.JSONDecodeError,TypeError)as exc:raise ValueError('strict JSON object required')from exc
    if not isinstance(value,dict):raise ValueError('JSON object required')
    return value


def parse_diagnosis(text,code,scope,*,fixed_input=None):
    value=json_object(text)
    status=value.get('status')
    if status not in ('defect','no_defect_in_scope','uncertain'):raise ValueError('status required')
    value['taxonomy_error']=validate_taxonomy(value.get('taxonomy_error'))
    if status=='uncertain':return value
    for key in ['span','actual','expected','mechanism']:
        if not isinstance(value.get(key),str):raise ValueError(key+' text required')
    if not value['mechanism'].strip():raise ValueError('mechanism required')
    if fixed_input is not None:
        if 'input'in value and value['input']!=fixed_input:raise ValueError('continuation input differs from observed input')
        value['input']=fixed_input
    if not isinstance(value.get('input'),str):raise ValueError('concrete input text required')
    spans=source_spans(code,value['span'])
    if status=='defect'and(not spans or not value['taxonomy_error']):raise ValueError('defect needs linked source span and official labels')
    if status=='no_defect_in_scope'and value['taxonomy_error']:raise ValueError('clean contradicts nonempty labels')
    # Domain validity is separate from serialization. Invalid inputs remain
    # schema-complete but cannot execute or become trustworthy witnesses.
    return value|{'span_matches':spans,'input_text':value['input'],'input':pack_input(scope,value['input'])}
