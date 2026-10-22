"""A single silent source-consistency check; original R15 pair and controller."""
from contextlib import contextmanager
from src.task3 import round15

INSTRUCTION=(
 ' Trước khi xuất JSON, kiểm lại cặp kết quả bằng việc đối chiếu từng nhận định '
 'trong feedback với đúng biểu thức và luồng xử lý đang có, rồi với yêu cầu đề. '
 'Loại nhận định không khớp mã; không dùng lỗi giả định sau khi sửa một phần để '
 'kết luận về mã gốc. Chỉ giữ taxonomy_error được cùng bằng chứng hỗ trợ. '
 'Thực hiện kiểm tra này nội bộ, không viết phân tích hoặc thêm trường.'
)


def messages(record,examples,*,retry=None):
    result=round15.build_messages(record,examples,retry=retry)
    result[0]['content']+=INSTRUCTION
    return result


def fitted(record,examples,tokenizer,config,*,retry=None):
    result=messages(record,examples,retry=retry)
    count=len(tokenizer.apply_chat_template(result,tokenize=True,add_generation_prompt=True))
    if count+int(config['max_new_tokens'])>int(config.get('context_limit',16384)):
        raise ValueError('full source exceeds context; never truncate source')
    return result,dict(input_tokens=count,examples_used=len(examples),examples_dropped=0)


@contextmanager
def adapter():
    from src.task3 import round15_runner
    original=round15_runner.fitted_messages
    round15_runner.fitted_messages=fitted
    try:yield
    finally:round15_runner.fitted_messages=original
