"""Reproducible artificial demonstrations derived exclusively from train exams."""
import hashlib
from src.task3.compiler import check_cpp_syntax
from src.task3.dataset import load_prepared
from src.task3.schema import code_hash
from src.task3.round14_eval import _families

UPPER='''#include <iostream>
#include <string>
using namespace std;
string chuyenHoa(string text) {
    for (char& ch : text) {
        if (ch >= 'A' && ch <= 'Z') ch = ch - 'A' + 'a';
    }
    return text;
}
int main() {
    string text;
    cin >> text;
    cout << chuyenHoa(text);
}
'''
GCD='''#include <iostream>
using namespace std;
int uocChung(int a, int b) {
    while (b != 0) {
        int du = a % b;
        a = b;
        b = du;
    }
    return a;
}
int main() {
    int n;
    cin >> n;
    int result = 0;
    for (int pos = 0; pos < n; ++pos) {
        int value;
        cin >> value;
        result = uocChung(result, value);
    }
    cout << result;
}
'''
FEEDBACK={
 1:('Bài còn điểm chưa đáp ứng yêu cầu. Em hãy đối chiếu lại kết quả với đề.',
    'Bài xử lý đúng yêu cầu trên dãy số nguyên dương hợp lệ.'),
 2:('Hàm chuyenHoa đổi chữ hoa thành chữ thường, nên đầu vào aB cho ra ab thay vì AB như đề yêu cầu.',
    'Hàm uocChung dùng số dư đúng bước Euclid; main đọc đủ n số và tích lũy GCD đúng trên dãy số nguyên dương hợp lệ.'),
 3:('Hàm chuyenHoa đang đổi chữ hoa thành chữ thường, ngược yêu cầu. Hãy chỉ chuyển các ký tự từ a đến z sang chữ hoa tương ứng, giữ nguyên ký tự khác.',
    'Hàm uocChung và vòng đọc trong main thực hiện đúng GCD của dãy số nguyên dương hợp lệ; chưa thấy lỗi cần sửa.'),
 4:('Hàm chuyenHoa chuyển ngược chiều viết hoa. Thay hàm bằng:\nstring chuyenHoa(string text) {\n    for (char& ch : text) {\n        if (ch >= \'a\' && ch <= \'z\') ch = ch - \'a\' + \'A\';\n    }\n    return text;\n}',
    'Bài đọc đủ n số và tính GCD bằng Euclid đúng trên dãy số nguyên dương hợp lệ; chưa cần thay mã.')}


def make_bank(data_dir,development_family_pool):
    rows=[r for s in ('real-train','synthetic-train') for r in load_prepared(data_dir,s)]
    by_id={r.sample_id:r for r in rows};families=_families(rows)
    definitions=[('upper-direction','SYN-UPPER-0006',UPPER,['Lỗi logic'],
                  'aB -> ab, yêu cầu AB; không có source query trong lựa chọn.'),
                 ('gcd-clean','SYN-GCDARR-0007',GCD,[],
                  'Euclid dùng số dư; invariant result=GCD(prefix), duyệt đủ n số dương. Không mảng cố định.')]
    bank=[]
    for level in range(1,5):
        for idx,(name,parent_id,code,taxonomy,reason) in enumerate(definitions):
            parent=by_id[parent_id]
            if not parent.split.endswith('-train'):raise ValueError('train parent required')
            identities={'code_hash':code_hash(code),'renamed_code_hash':code_hash(code,renamed=True)}
            for r in development_family_pool:
                if (r.sample_id==parent_id or families[parent_id]==families[r.sample_id]
                        or identities['code_hash']==r.code_hash
                        or identities['renamed_code_hash']==code_hash(r.code,renamed=True)):
                    raise ValueError('bank/evaluation family or code contamination')
            compiler=check_cpp_syntax(code,standard='c++11',timeout_s=3)
            if compiler['status']!='compiled':raise ValueError('artificial example must compile')
            bank.append({'id':f'artificial-{name}-L{level}', 'level':level,'statement':parent.statement,
                         'problems':parent.problems,'grading_policy':parent.grading_policy,'code':code,
                         'compiler':{k:compiler[k] for k in ('status','diagnostic')},
                         'output':{'taxonomy_error':taxonomy,'feedback':FEEDBACK[level][idx]},
                         'provenance':{'parent_id':parent_id,'source':parent.split,'family':families[parent_id],
                         'kind':'artificial submission from unchanged train exam','review_status':'assistant-reviewed, not human-verified',
                         'parent_code_sha256':hashlib.sha256(parent.code.encode()).hexdigest(),
                         'statement_sha256':hashlib.sha256(parent.statement.encode()).hexdigest(),
                         'source_sha256':hashlib.sha256(code.encode()).hexdigest(),**identities,
                         'selection_reason':reason,'teacher_feedback_copied':False,'public_used':False,
                         'level_assignment':'bank-only; dataset gold unchanged',
                         'review_note':'ASCII letters as in train uppercase implementation; valid positive integer input for GCD. Fully read source, not compiler-only clean.'}})
    return bank
