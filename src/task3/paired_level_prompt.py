"""Alternative single delta: Level-specific prose frames, no content replacement."""
from contextlib import contextmanager
from src.task3 import round15
FRAMES={
 1:' Khuôn feedback Level 1: đúng một câu báo bài còn có vấn đề nếu kết luận có lỗi; nếu chưa tìm thấy lỗi thì nhận xét có giới hạn. Không ghi bất kỳ vị trí, tên biến/hàm, cơ chế lỗi hoặc cách sửa.',
 2:' Khuôn feedback Level 2: một hoặc hai câu nêu vị trí, mô tả mã hiện tại và nguyên nhân lệch yêu cầu. Dừng tại mô tả; không viết thao tác sửa, biểu thức hoặc giá trị thay thế.',
 3:' Khuôn feedback Level 3: nếu có lỗi, câu đầu nêu lỗi chính có căn cứ và nguyên nhân; câu tiếp theo chỉ một hướng sửa cụ thể cho chính lỗi đó. Nếu bài đúng thì nhận xét đúng có căn cứ, không bịa hướng sửa. Không đưa lời giải đầy đủ.',
 4:''}


def messages(record,examples,*,retry=None):
    result=round15.build_messages(record,examples,retry=retry)
    result[0]['content']+=FRAMES[int(record.target_feedback_level[6])]
    return result


def fitted(record,examples,tokenizer,config,*,retry=None):
    result=messages(record,examples,retry=retry)
    count=len(tokenizer.apply_chat_template(result,tokenize=True,add_generation_prompt=True))
    if count+int(config['max_new_tokens'])>int(config.get('context_limit',16384)):raise ValueError('full source exceeds context; never truncate source')
    return result,dict(input_tokens=count,examples_used=len(examples),examples_dropped=0)


@contextmanager
def adapter():
    from src.task3 import round15_runner
    original=round15_runner.fitted_messages;round15_runner.fitted_messages=fitted
    try:yield
    finally:round15_runner.fitted_messages=original
