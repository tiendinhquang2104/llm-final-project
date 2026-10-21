"""One offline Level-2-only prompt candidate, with the untouched R15 controller.

No demonstrations, extra input fields, intermediate reasoning or schema changes.
Adapters are sequential-only and restore controller functions even on failure.
"""
from __future__ import annotations
from contextlib import contextmanager
from src.task3 import round15

VERSION = 'level2-diagnostic-D-v1'
L2_INSTRUCTION = (
    ' Riêng requested_level=2: chỉ chẩn đoán theo định nghĩa trong label_space.json: '
    'chỉ ra lỗi ở đâu và nguyên nhân là gì; không đưa cách sửa cụ thể, không đưa code sửa. '
    'Trước khi viết phản hồi, tự xác định vị trí hoặc biểu thức đang có trong source, '
    'cơ chế làm sai yêu cầu trên miền đầu vào hợp lệ, và hậu quả có căn cứ. '
    'Sau đó viết một câu chẩn đoán cuối kết nối vị trí, cơ chế và hậu quả; không xuất suy luận trung gian. '
    'Trích biểu thức đang sai để mô tả hành vi khác với đưa biểu thức đã sửa: chỉ được trích cái đang có, '
    'không được đưa biểu thức hay giá trị mới thay thế. Mô tả một thành phần bị thiếu là chẩn đoán; '
    'bảo thêm thành phần đó là chỉ dẫn sửa và bị cấm. '
    'Không đưa mệnh lệnh hay khuyến nghị thao tác: thêm, bỏ, đổi, thay, dùng, khởi tạo, chuyển, viết lại; '
    'không nói nên/cần/phải kèm thao tác cụ thể, không hướng dẫn từng bước hoặc code block. '
    'Đối chiếu khai báo và trạng thái biến thực tế: biến đã là long long hoặc đã được khởi tạo '
    'thì không bịa lỗi kiểu hay khởi tạo; không suy lỗi từ đầu vào ngoài giả thiết. '
    'Nếu không đủ căn cứ, nói rõ giới hạn nhận định, không bịa lỗi và không khen bài đúng hoàn toàn. '
    'Giữ taxonomy_error tự dự đoán từ đúng 10 nhóm chính thức; chỉ xuất JSON hai khóa taxonomy_error và feedback.'
)


def messages(record, examples, *, arm, retry=None):
    if arm not in ('A', 'D'):
        raise ValueError('arm must be A/D')
    result = round15.build_messages(record, examples, retry=retry)
    if arm == 'D' and int(record.target_feedback_level[6]) == 2:
        result[0]['content'] += L2_INSTRUCTION
    return result


def fitted(record, examples, tokenizer, config, *, arm, retry=None):
    if examples:
        raise ValueError('this experiment is zero-shot')
    result = messages(record, [], arm=arm, retry=retry)
    tokens = len(tokenizer.apply_chat_template(result, tokenize=True, add_generation_prompt=True))
    if tokens + int(config['max_new_tokens']) > int(config.get('context_limit', 16384)):
        raise ValueError('full query exceeds budget; never truncate source')
    return result, {'input_tokens': tokens, 'examples_used': 0, 'examples_dropped': 0}


@contextmanager
def adapter(arm, *, guard='old'):
    import src.task3.round15_runner as runner
    if arm not in ('A','D') or guard not in ('old','new'):
        raise ValueError('unknown arm/guard')
    original_prompt, original_guard = runner.fitted_messages, runner.disclosure_violations
    runner.fitted_messages = lambda r,e,t,c,**kw: fitted(r,e,t,c,arm=arm,**kw)
    if guard == 'new':
        from src.task3.level2_guard import disclosure_violations
        runner.disclosure_violations = disclosure_violations
    try:
        yield
    finally:
        runner.fitted_messages, runner.disclosure_violations = original_prompt, original_guard
