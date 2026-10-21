"""Offline feedback comparison. No public loader, teacher prompts, or training path."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import re

from src.task3 import round15
from src.task3.schema import code_hash, _CPP_TOKEN

VERSION = 'feedback-prompt-offline-1'
SYSTEM_B = round15.SYSTEM + (
    ' Đọc kỹ yêu cầu và toàn bộ source trước khi nhận định. Nếu có lỗi, chọn một finding cốt lõi '
    'có bằng chứng chắc nhất từ mã, ưu tiên lỗi ảnh hưởng kết quả hoặc chặn bài chạy. '
    'Không liệt kê thêm lỗi chưa kiểm chứng. Đặc biệt không suy lỗi chỉ vì cách viết khác lời giải quen thuộc. '
    'Level 1: chỉ kết luận bài cần rà soát hoặc đang phù hợp; không ám chỉ đoạn mã hay cơ chế lỗi. '
    'Level 2: gọi đúng đoạn xử lý hoặc biểu thức trong source và giải thích vì sao nó gây sai yêu cầu; '
    'chỉ chẩn đoán, không nói thao tác thay đổi mã. Tránh lời chung chung thay cho chẩn đoán. '
    'Level 3: sau chẩn đoán, nêu một hướng sửa cục bộ khả thi gắn với lỗi đó; không viết lại cả bài. '
    'Level 4: chẩn đoán rồi trình bày cách sửa hoặc lời giải đúng các ràng buộc của đề. '
    'Nếu không thấy lỗi có căn cứ, nói rõ phạm vi nhận định và không bịa lỗi để đủ nội dung. '
    'Chỉ sinh trực tiếp JSON cuối gồm taxonomy_error và feedback; không xuất phân tích trung gian.'
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def seal(path, files, metadata):
    from src.task3.dataset import write_json
    path=Path(path)
    if path.exists():
        raise ValueError('seal already exists; do not replace frozen experiment')
    write_json(path, {'metadata': metadata, 'files': {str(Path(p).resolve()): sha(p) for p in files}})


def verify_seal(path):
    value=json.loads(Path(path).read_text())
    for filename, expected in value['files'].items():
        if not Path(filename).is_file() or sha(filename) != expected:
            raise ValueError('frozen artifact hash mismatch: '+filename)
    return value


def _shingles(code, structural=False):
    tokens=[]
    keywords=set('int long short char float double bool void if else for while do return break continue class struct public private const static using namespace std include true false nullptr new delete auto unsigned signed switch case default sizeof template typename'.split())
    for m in _CPP_TOKEN.finditer(code):
        t=m.group()
        if t.startswith(('//','/*')):continue
        if structural and re.fullmatch('[A-Za-z_]\\w*', t) and t not in keywords:t='ID'
        tokens.append(t)
    return {tuple(tokens[i:i+5]) for i in range(max(0,len(tokens)-4))}


def similarity(a,b):
    def jaccard(x,y):return len(x&y)/len(x|y) if x|y else 1.0
    return {'token_identity':code_hash(a)==code_hash(b),
            'renamed_identity':code_hash(a,renamed=True)==code_hash(b,renamed=True),
            'lexical_jaccard':jaccard(_shingles(a),_shingles(b)),
            'structural_jaccard':jaccard(_shingles(a,True),_shingles(b,True))}


def validate_bank(bank, training, evaluation):
    for ex in bank:
        r=training.get(ex.get('sample_id'))
        if r is None or r.source=='public' or r.split not in ('real-train','synthetic-train'):
            raise ValueError('bank requires verified train membership')
        p=ex.get('provenance',{})
        if p.get('partition')!=r.split or p.get('author')!='agent-reviewed':
            raise ValueError('bank train review provenance mismatch')
        if ex.get('code')!=r.code or ex.get('statement')!=r.statement or ex.get('family')!=r.exam_id:
            raise ValueError('bank train source/statement binding mismatch')
        if type(ex.get('level')) is not int or ex['level'] not in range(1,5):raise ValueError('invalid example Level')
        round15.process_response(json.dumps(ex['output'],ensure_ascii=False),ex['level'])
        for other in evaluation:
            s=similarity(r.code,other.code)
            if (r.sample_id==other.sample_id or (r.group_key and r.group_key==other.group_key)
                    or s['token_identity'] or s['renamed_identity']
                    or max(s['lexical_jaccard'],s['structural_jaccard'])>=.75):
                raise ValueError('example overlaps evaluation source')
    return bank


def choose_examples(record,bank):
    eligible=[ex for ex in bank if ex['level']==int(record.target_feedback_level[6]) and ex['family']!=record.exam_id]
    eligible.sort(key=lambda ex:digest([record.code,ex['sample_id']]))
    selected=[];families=set()
    for ex in eligible:
        if ex['family'] not in families:
            selected.append(ex);families.add(ex['family'])
        if len(selected)==2:break
    return selected


def messages(record,examples,arm,*,retry=None):
    if arm not in ('A','B','C'):raise ValueError('offline arm must be A/B/C')
    # Round15 renderer already whitelists query and problem keys. Examples use the
    # same whitelist here; provenance, references and teacher fields cannot leak.
    clean=[]
    for ex in examples:
        clean.append({'level':ex['level'],'statement':ex['statement'],'code':ex['code'],
            'problems':[{k:p[k] for k in ('pid','statement','prototype') if k in p} for p in ex.get('problems',[])],
            'grading_policy':ex.get('grading_policy',''),
            'compiler':{k:ex.get('compiler',{}).get(k,'') for k in ('status','diagnostic')},'output':ex['output']})
    result=round15.build_messages(record,clean,retry=retry)
    if arm in ('B','C'):result[0]['content']=SYSTEM_B
    return result


def fitted(record,examples,tokenizer,config,*,arm,retry=None):
    selected=choose_examples(record,examples) if arm=='C' else []
    original=len(selected)
    while True:
        result=messages(record,selected,arm,retry=retry)
        tokens=len(tokenizer.apply_chat_template(result,tokenize=True,add_generation_prompt=True))
        if tokens+int(config['max_new_tokens'])<=int(config.get('context_limit',16384)):
            return result,{'input_tokens':tokens,'examples_used':len(selected),'examples_dropped':original-len(selected)}
        if not selected:raise ValueError('full query exceeds budget; never truncate source')
        selected.pop()  # Locked rule: drop final selected demonstration first.


@contextmanager
def prompt_adapter(arm):
    """Sequential-only adapter; preserve every original controller decision."""
    import src.task3.round15_runner as runner
    original=runner.fitted_messages
    if arm!='A':
        runner.fitted_messages=lambda r,e,t,c,**kw:fitted(r,e,t,c,arm=arm,**kw)
    try:yield
    finally:runner.fitted_messages=original


def proxy_score(v,level,clean):
    if any(v.get(k,False) for k in ('unknown','false_technical_claim','false_clean','level_violation')):return 0.0
    if level<=2 and v.get('repair_disclosure'):return 0.0
    if level==1:
        return 1.0 if v.get('status_correct') else .5 if v.get('generic') else 0.0
    if clean:return 1.0 if v.get('status_correct') and not v.get('generic') else 0.0
    if v.get('generic'):return 0.0
    correct=bool(v.get('location_correct'))+bool(v.get('cause_correct'))
    if level==2:return 1.0 if correct==2 else .5 if correct==1 else 0.0
    if level in (3,4):
        return 1.0 if correct==2 and v.get('feasible_repair') else .5 if correct>=1 else 0.0
    raise ValueError('Level must be 1..4')
