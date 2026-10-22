"""One internal defect-decision→label-mapping prompt delta; native output/guard unchanged."""
from contextlib import contextmanager
from src.task3 import round15

VERSION='round24-decide-then-map-v1'
INSTRUCTION=(
 ' Trước khi viết JSON cuối, tự tách hai quyết định nội bộ. '
 'Thứ nhất, xác định có lỗi nào được chứng minh từ yêu cầu và source hay không: '
 'đối chiếu điều kiện, khai báo, trạng thái và luồng xử lý thực tế; không biến giả thiết '
 'đầu vào thành nghĩa vụ kiểm tra đầu vào, không suy lỗi từ cách viết khác lời giải quen thuộc. '
 'Tách nhận xét style khỏi lỗi làm sai hành vi; thiếu căn cứ không đồng nghĩa bài đúng hoàn toàn. '
 'Thứ hai, chỉ ánh xạ các lỗi đã có bằng chứng sang đúng10 tên nhóm đã liệt kê. '
 'Không gán nhóm chỉ vì source có vòng lặp, mảng hay hàm, và không mặc định cộng Logic vào mọi lỗi. '
 'Nhãn và feedback phải nói về cùng lỗi có căn cứ. '
 'Sau hai quyết định, viết feedback trực tiếp đúng requested_level theo các quy tắc ở trên; '
 'không xuất các bước nội bộ, không thêm khóa JSON. Giữ đúng hai khóa taxonomy_error và feedback.'
)


def messages(record,examples,*,arm,retry=None):
    if arm not in ['R15','C']:raise ValueError('unknown arm')
    if examples:raise ValueError('zero-shot comparison only')
    result=round15.build_messages(record,[],retry=retry)
    if arm=='C':result[0]['content']+=INSTRUCTION
    return result


def fitted(record,examples,tokenizer,config,*,arm,retry=None):
    result=messages(record,examples,arm=arm,retry=retry)
    count=len(tokenizer.apply_chat_template(result,tokenize=True,add_generation_prompt=True))
    if count+int(config['max_new_tokens'])>int(config.get('context_limit',16384)):raise ValueError('full source exceeds context; no truncation')
    return result,{'input_tokens':count,'examples_used':0,'examples_dropped':0}


@contextmanager
def adapter(arm):
    import src.task3.round15_runner as runner
    original=runner.fitted_messages
    runner.fitted_messages=lambda r,e,t,c,**kw:fitted(r,e,t,c,arm=arm,**kw)
    try:yield
    finally:runner.fitted_messages=original
