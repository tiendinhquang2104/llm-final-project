"""Eight artificial train submissions, eight families, no copied teacher prose."""
import hashlib
from src.task3.compiler import check_cpp_syntax
from src.task3.schema import code_hash
from src.task3.round17 import validate_bank

# Each recipe is used once, at exactly one Level. No bank source is re-levelled.
RECIPES=[
(1,'SYN-COUNTVOWEL',True,'''#include <iostream>
#include <string>
using namespace std;
int demNguyenAm(string text) {
    int count = 0;
    for (char ch : text) if (ch == 'a') ++count;
    return count;
}
int main() { string text; cin >> text; cout << demNguyenAm(text); }
''','Bài còn điểm chưa đáp ứng yêu cầu. Em hãy đối chiếu kết quả với đề.',
 'Chỉ đếm a, thiếu e/i/o/u. Input e có output0 thay1. L1 không lộ cause/location.'),
(1,'SYN-FACT',False,'''#include <iostream>
using namespace std;
int main() {
    int n; cin >> n;
    unsigned long long result = 1;
    for (int k = 2; k <= n; ++k) result *= k;
    cout << result;
}
''','Bài xử lý đúng yêu cầu trong miền đầu vào của đề.',
 '0! và1! bằng1; invariant result=k!; 20! =2432902008176640000 fits uint64. Đề0..20.'),
(2,'SYN-POWER',True,'''#include <iostream>
using namespace std;
int main() {
    long long coSo, soMu;
    cin >> coSo >> soMu;
    cout << coSo * soMu;
}
''','Trong main, biểu thức coSo * soMu tính tích hai đầu vào, không phải lũy thừa. Với 2 và 3, chương trình in 6 trong khi đề yêu cầu 8.',
 'Counterexample2,3: multiplication6 vs exponent8. Chẩn đoán không hướng sửa.'),
(2,'SYN-SECONDMAX',False,'''#include <iostream>
using namespace std;
int main() {
    int n; cin >> n;
    long long first, second; cin >> first >> second;
    if (first < second) { long long tmp = first; first = second; second = tmp; }
    for (int k = 2; k < n; ++k) {
        long long value; cin >> value;
        if (value > first) { second = first; first = value; }
        else if (value > second) second = value;
    }
    cout << second;
}
''','Bài duy trì đúng hai giá trị lớn nhất và in giá trị lớn thứ hai với dãy phân biệt có ít nhất hai phần tử.',
 'Miền hợp lệ của giá trị lớn thứ hai: n>=2. Hai đầu tiên chuẩn hóa; mỗi bước bảo toàn largest/second-largest, gồm số âm. Không mảng cố định.'),
(3,'SYN-COUNTUPPER',True,'''#include <iostream>
#include <string>
using namespace std;
int soHoa(string word) {
    int answer = 0;
    for (char ch : word) if (ch >= 'a' && ch <= 'z') ++answer;
    return answer;
}
int main() { string word; cin >> word; cout << soHoa(word); }
''','Hàm soHoa đang đếm chữ thường thay vì chữ hoa, nên aBC cho ra 1 thay vì 2. Hãy đổi điều kiện để chỉ nhận ký tự từ A đến Z.',
 'aBC has1lowercase vs2uppercase. Chuyển range A..Z là sửa đủ, giữ bộ đếm.'),
(3,'SYN-MAXARR',False,'''#include <iostream>
using namespace std;
int main() {
    int n; cin >> n;
    long long best; cin >> best;
    int remaining = n - 1;
    while (remaining > 0) {
        long long value; cin >> value;
        if (best < value) best = value;
        --remaining;
    }
    cout << best;
}
''','Bài đọc đủ dãy không rỗng và duy trì đúng giá trị lớn nhất; chưa thấy lỗi cần sửa trong miền đầu vào hợp lệ.',
 'Max xác định với n>=1; best gán từ input trước dùng, invariant max(prefix), gồm mọi dãy âm. Không mảng/giới hạn giả.'),
(4,'SYN-DIGITSUM',True,'''#include <iostream>
using namespace std;
long long tongChuSo(unsigned long long number) {
    long long total = 1;
    while (number > 0) {
        total *= number % 10;
        number /= 10;
    }
    return total;
}
int main() { unsigned long long number; cin >> number; cout << tongChuSo(number); }
''','Hàm tongChuSo đang nhân các chữ số và trả 1 khi đầu vào là 0. Thay hàm bằng:\nlong long tongChuSo(unsigned long long number) {\n    long long total = 0;\n    while (number > 0) {\n        total += number % 10;\n        number /= 10;\n    }\n    return total;\n}',
 '12->2 thay3;0->1 thay0. Patch total0 và += xử lý0 cùng các chữ số. Tổng <=180 với uint64, không overflow.'),
(4,'SYN-PRIME',False,'''#include <iostream>
using namespace std;
bool nguyenTo(long long x) {
    if (x < 2) return false;
    for (long long divisor = 2; divisor <= x / divisor; ++divisor)
        if (x % divisor == 0) return false;
    return true;
}
int main() { long long x; cin >> x; cout << (nguyenTo(x) ? "True" : "False"); }
''','Hàm nguyenTo loại số nhỏ hơn 2 và kiểm tra đủ ước đến căn bậc hai; cách so sánh bằng phép chia tránh tràn khi tính bình phương. Chưa thấy lỗi cần sửa với đầu vào hợp lệ.',
 'Composite>=2 cóước<=sqrt; d<=x/d tương đươngd*d<=x khi d>0 nhưng tránh overflow. Nhánhx<2 xửlý âm,0,1. No runtime claim.')]


def make_bank(train,evaluation):
    bank=[]
    for index,(level,family,defect,code,feedback,review) in enumerate(RECIPES):
        candidates=sorted((r for r in train if r.exam_id==family),key=lambda r:r.sample_id)
        if not candidates:raise ValueError('train family missing: '+family)
        parent=candidates[0]  # Only family and ID metadata, never labels/feedback.
        compiler=check_cpp_syntax(code,compiler='/usr/bin/g++',standard='c++11',timeout_s=3)
        if compiler['status']!='compiled':raise ValueError('artificial source syntax failure')
        bank.append({'id':f'r17-{family}-L{level}','level':level,'statement':parent.statement,
            'problems':parent.problems,'grading_policy':parent.grading_policy,'code':code,
            'compiler':{k:compiler[k] for k in ('status','diagnostic')},
            'output':{'taxonomy_error':['Lỗi logic'] if defect else [],'feedback':feedback},
            'provenance':{'parent_id':parent.sample_id,'source':parent.split,'family':family,
                'kind':'artificial full submission from unchanged train exam; used once at this Level',
                'review_status':'assistant-reviewed, not human-verified','teacher_feedback_copied':False,
                'v2_feedback_read_for_reference':False,'selection':'fixed family design + smallest eligible train ID; no query-gold or query-feedback selection',
                'source_sha256':hashlib.sha256(code.encode()).hexdigest(),'renamed_code_hash':code_hash(code,renamed=True),
                'parent_source_sha256':hashlib.sha256(parent.code.encode()).hexdigest(),
                'statement_sha256':hashlib.sha256(parent.statement.encode()).hexdigest(),'source_review':review}})
    return validate_bank(bank,evaluation)
