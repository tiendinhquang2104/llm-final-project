#!/usr/bin/env python3
"""Source-reviewed SFT targets; gold annotations are comparison metadata only."""
import json
from dataclasses import asdict,replace
from pathlib import Path
import sys
REPO=Path(__file__).resolve().parents[1];sys.path.insert(0,str(REPO))
from scripts.task3_round18 import ROOT,records,verify,sha,metadata
from src.task3.dataset import load_task3,load_prepared,write_json
from src.task3.schema import code_hash
from src.task3.compiler import check_cpp_syntax
from src.task3.round14 import sanitize
from src.task3.round14_runner import digest
from src.task3.two_stage import diagnosis_messages,feedback_messages,parse_diagnosis

# Hand-authored short review tuples: official group, exact source quote, location,
# source-based diagnosis/counterexample, feasible direction (no copied teacher target).
REVIEWS={
'SYN-COUNT-0000':[],
'SYN-COUNTEVEN-0001':[],
'SYN-GEN-0001':[],
'SYN-UPPER-0003':[],
'SYN-COUNT-0007':[
 ('Lỗi vòng lặp','for (int i = 1; i < n; )','prob3','Với n=2, i giữ nguyên bằng1 nên vòng lặp không kết thúc.','Tăng chỉ số duyệt sau mỗi lượt để tiến tới điều kiện dừng.')],
'SYN-COUNTEVEN-0003':[
 ('Lỗi mảng/chuỗi','tong = arr[i + 1].b;','prob3','Khi phần tử hiện tại nhỏ hơn tong, mã lại lưu phần tử kế tiếp. Dãy b=[5,1,3] trả3 thay1.','Cập nhật giá trị nhỏ nhất bằng chính phần tử vừa được so sánh; giữ chỉ số trong miền dữ liệu.')],
'SYN-GEN-0003':[
 ('Lỗi vòng lặp','i < n - 1','prob3','Vòng lặp bỏ qua phần tử cuối. Với a=[1,9], hàm trả1 thay9.','Cho vòng duyệt bao phủ cả phần tử cuối trong miền0..n-1.')],
'SYN-GEN-0016':[
 ('Lỗi hàm','return 0;','prob3','Hàm chưa tính max a mà luôn trả0; một bản ghi a=7 phải trả7.','Triển khai tìm max a từ các bản ghi thực tế.'),
 ('Lỗi vòng lặp','prob2(arr, n - 1)','prob4','Truyền n-1 khiến phép tính tổng bỏ bản ghi cuối; một bản ghi a=7 bị in0.','Truyền đủ số bản ghi cần xử lý vào hàm tính tổng.')],
'SYN-RANGE-0014':[
 ('Lỗi hard-code','ifstream f("data.csv");','prob1','Hàm bỏ qua filename và luôn đọc data.csv; truyền rng.csv không được sử dụng.','Mở tệp theo tham số filename, đồng thời kiểm tra trạng thái đọc.')],
'SYN-SUMB-0007':[
 ('Lỗi edge case','if (n == 1) return 0;','prob2','Một bản ghi b=5 có tổng5 nhưng nhánh riêng trả0.','Để trường hợp một phần tử được tính như quy tắc tổng chung.'),
 ('Lỗi logic','kq3 = 0;','prob3','Khởi tạo0 và bắt đầu i=1 bỏ bản ghi đầu, sai cả dãy a âm. Một bản ghi a=-2 trả0 thay-2.','Khởi tạo max từ phần tử đầu và duyệt các phần tử còn lại.'),
 ('Lỗi nhập/xuất','if (arr[i].b > 0) t += arr[i].b;','prob4','Chỉ cộng b dương nên không in tổng tất cả b; một bản ghi b=-3 in0 thay-3.','In tổng b của toàn bộ bản ghi, kể cả số âm.')],
'SYN-SUMPAIR-0003':[
 ('Lỗi logic','kq3 = 0;','prob3','Khởi tạo0 và duyệt từ i=1 bỏ a[0]. Một bản ghi a=5 phải trả5 nhưng trả0; dãy âm cũng sai.','Khởi tạo max bằng a đầu tiên rồi duyệt phần còn lại.')],
'SYN-UPPER-0006':[
 ('Lỗi hàm','int main() {\n    return 0;','main','Hàm chuyển chữ hoa không được gọi; main kết thúc ngay, nên input a không nhận output A.','Đọc chuỗi, gọi hàm chuyển đổi và in giá trị trả về.')],
'SYN-UPPER-0007':[
 ('Lỗi biên dịch','char s[1005]','main','Thiếu dấu chấm phẩy kết thúc khai báo mảng; compiler báo lỗi trước cin.','Kết thúc khai báo mảng bằng dấu chấm phẩy.')],
'SYN-COUNTVOWEL-0004':[
 ('Lỗi vòng lặp','int i = 1','countVowel','Bắt đầu từ1 bỏ ký tự đầu. Input a cho0 thay1.','Duyệt từ ký tự đầu đến trước độ dài chuỗi.')],
'SYN-COUNTVOWEL-0012':[
 ('Lỗi logic','demNguyenAm = demNguyenAm - 1;','main','Bộ đếm giảm khi gặp nguyên âm; input a trả-1 thay1.','Tăng bộ đếm cho mỗi nguyên âm gặp được.')],
'SYN-MAXARR-0005':[
 ('Lỗi vòng lặp','i < n - 1','main','Chỉ đọc n-1 giá trị, bỏ phần tử cuối: n=2,dãy1 9 in1 thay9.','Bao phủ đủ n giá trị, tính cả giá trị đầu đã đọc.'),
 ('Lỗi nhập/xuất','cout << "Nhap n: ";','main','In thêm lời nhắc trước số kết quả, không đúng định dạng chỉ in giá trị lớn nhất.','Bỏ lời nhắc khỏi output nộp bài.')],
'SYN-PALIN-0005':[
 ('Lỗi mảng/chuỗi','s[i + 1] != s[n - 1 - i]','main','So sánh lệch cặp đối xứng: input12 so sánh ký tự thứ hai với chính nó rồi inTrue, phảiFalse.','So sánh ký tự tại vị trí i với vị trí đối xứng n-1-i.')],
'SYN-PALIN-0022':[
 ('Lỗi thuật toán','rev = rev * 10 - n % 10;','doiXung','Dựng số đảo bằng phép trừ nên số đảo âm. Input11 choFalse dù phảiTrue.','Dựng số đảo bằng cách thêm chữ số vừa tách vào sau phần đã dựng, lưu ý giới hạn kiểu số.')],
'EX01-S101':[
 ('Lỗi logic','delete deleted;','prob4','Khi xóa node, head hoặc liên kết next của node trước không được đổi. Xóa node đầu làm head trỏ vùng nhớ đã giải phóng.','Cập nhật head khi xóa đầu; với node khác cập nhật next của node trước rồi mới giải phóng.'),
 ('Lỗi hàm','Node* prob2(General* generals, int n)','toàn bộ source','Có prob1,prob2,prob4 nhưng thiếu định nghĩa prob3 theo yêu cầu tìm tướng nhiều tuổi nhất.','Bổ sung hàm prob3 duyệt danh sách, tính tuổi theo era và giữ phần tử đầu khi hòa.'),
 ('Lỗi nhập/xuất','return x;','prob1','Hàm tăng i sau mỗi bản ghi nhưng không gán lại tham số n; số bản ghi trả cho bên gọi không phản ánh số dòng thực đọc.','Đếm dữ liệu đọc thành công và cập nhật tham số n theo số bản ghi đó.')],
'EX01-S102':[
 ('Lỗi logic','return new Node{g, nullptr};','addTail','Nhánh danh sách rỗng chỉ trả node mới mà không gán pHead; prob2 bỏ qua giá trị trả về nên head vẫn null.','Gán node mới cho pHead khi danh sách ban đầu rỗng.'),
 ('Lỗi logic','pPrev -> next = pCurr -> next;','prob4','Khi node đầu có nationality cần xóa, pPrev vẫn null nhưng bị dereference.','Xử lý riêng cập nhật head khi xóa đầu và chỉ truy cập pPrev khi nó tồn tại.')]
}
CLEAN_BASIS={
'SYN-UPPER-0003':'Trong miền chuỗi ASCII không khoảng trắng, mỗi ký tự thường được đổi sang hoa, ký tự khác giữ nguyên, in chuỗi kết quả. TODO/comment không phải lỗi theo đề.',
'SYN-COUNT-0000':'Với file hợp lệ không rỗng và dữ liệu vừa int: đọc từng cặp vào vector, sao chép vào mảng động, n bằng số bản ghi, prob2 trả n, prob3 giữ min b, prob4 in n. File rỗng không có min nên cần quy ước từ đề; không chứng nhận miền ngoài giả thiết này.',
'SYN-COUNTEVEN-0001':'Với file hợp lệ không rỗng, vừa int: đọc đúng từng cặp, cấp phát theo số đọc, đếm từng a chia hết2 kể cả âm, giữ min b, in prob2. Đề chưa quy định min của file rỗng; kết luận sạch chỉ trong miền có min.',
'SYN-GEN-0001':'Với file hợp lệ không rỗng, tổng a vừa int: đọc vào vector rồi mảng động, n đúng số bản ghi, cộng tất cả a, giữ max a và in tổng. Không khẳng định xử lý file rỗng/overflow ngoài miền này.'}

def main():
 f=verify();out=ROOT/'targets.private.json';assert not out.exists(),'targets already frozen'
 synthetic={r.sample_id:r for r in load_task3(REPO/'data/raw/round18-new','synthetic')}
 real={r.sample_id:r for r in load_prepared(REPO/'data/processed/task3','real-train')}
 prepared_train={r.sample_id:r for r in load_prepared(REPO/'data/processed/task3','synthetic-train')}
 elig=set(prepared_train)
 protected=records('counterfactual')+records('evaluation')+load_prepared(REPO/'data/processed/task3','real-val')+load_prepared(REPO/'data/processed/task3','synthetic-heldout')
 denied={code_hash(r.code,renamed=True) for r in protected};denied_groups={r.group_key or r.original_submission_id for r in protected};denied_original={r.original_submission_id for r in protected}
 families=set(f['pilot_policy']['training_family_exclusions']);seen=set();rows=[];provenance=[]
 for sid,findings in REVIEWS.items():
  r=real[sid] if sid in real else synthetic[sid]
  if sid in prepared_train:r=replace(r,group_key=prepared_train[sid].group_key,split='synthetic-train')
  assert sid in real or sid in elig
  assert r.exam_id not in families
  identity=code_hash(r.code,renamed=True)
  assert identity not in denied|seen and r.original_submission_id not in denied_original and (r.group_key or r.original_submission_id) not in denied_groups,sid
  seen.add(identity)
  e=check_cpp_syntax(r.code,compiler='/usr/bin/g++',standard='c++11',timeout_s=3);e.pop('latency_s',None)
  clean=sanitize(r,e);labels=list(dict.fromkeys(x[0] for x in findings))
  diag={'status':'defect' if findings else 'clean','taxonomy_error':labels,
        'findings':[dict(zip(('label','quote','location','evidence'),x[:4])) for x in findings],
        'basis':'Chẩn đoán từ source/đề; compiler '+e['status']+'. Các giới hạn dung lượng/miền chưa rõ không tự thành lỗi đã xác nhận.' if findings else CLEAN_BASIS[sid]}
  parse_diagnosis(json.dumps(diag,ensure_ascii=False),clean)
  if 'Lỗi biên dịch' in labels:assert e['status']=='compile_error'
  target_rows=[{'sample_id':sid,'task':'diagnose','messages':diagnosis_messages(clean),'completion':json.dumps(diag,ensure_ascii=False)}]
  for level in (1,2,3):
   if not findings:feedback='Trong miền hợp lệ đã đối chiếu, bài đáp ứng yêu cầu. '+('Các trường hợp ngoài miền mô tả cần thêm quy ước từ đề.' if level>1 else '')
   elif level==1:feedback='Bài còn vấn đề chưa đáp ứng yêu cầu. Em hãy đối chiếu lại kết quả với đề.'
   elif level==2:feedback=' '.join(x[2]+': '+x[3] for x in findings)
   else:feedback=' '.join(x[2]+': '+x[3]+' Hướng sửa: '+x[4] for x in findings)
   target_rows.append({'sample_id':sid,'task':'feedback','level':level,'messages':feedback_messages(clean,diag,level),'completion':json.dumps({'feedback':feedback.strip()},ensure_ascii=False)})
  rows.extend(target_rows)
  provenance.append(metadata(r,{'labels_source_review':labels,'compiler_status':e['status'],'review':'assistant reviewed, not human verified','findings':[dict(zip(('label','quote','location','evidence','repair'),x)) for x in findings],'basis':diag['basis'],'target_sha256':[digest(x) for x in target_rows],'gold_disagreement':set(labels)!=set(r.gold_taxonomy or [])}))
 from src.task3.two_stage_data import require_historical_isolation
 require_historical_isolation(provenance,REPO)
 write_json(out,rows)
 manifest={'target_file_sha256':sha(out),'zip_sha256':f['zip_sha256'],'records':len(provenance),'examples':len(rows),'source_counts':{'real':sum(p['sample_id'].startswith('EX') for p in provenance),'synthetic':sum(p['sample_id'].startswith('SYN') for p in provenance)},'provenance':provenance,'evaluation_freeze_sha256':sha(ROOT/'freeze.json'),'split_policy':'all counterfactual/evaluation families excluded from train; exact/token/identifier-renamed identity, original and group excluded against both sets plus six real-val and old synthetic-heldout; each train code once before task/Level expansion','validation_policy':'fixed16 evaluation only, no during-train selection; exactly final one-epoch adapter','annotation_policy':'gold v2 unchanged and compared only; teacher feedback not copied; style-only vs scoped clean and missing implementation disagreements explicit','disputed_excluded':'whitespace-only correctness, invented style obligations, unspecified capacity/empty-file/overflow guarantees are not trained as unconditional claims; scoped clean basis states restrictions; no public data read for target selection','teacher_style_reference':'short Vietnamese locality/cause/direction; official label_space content rules take priority; no teacher text in inference'}
 write_json(ROOT/'targets-manifest.json',manifest);write_json(REPO/'reports/task3/TASK3_ROUND18_TARGET_PROVENANCE_20261020.json',manifest)
 print(len(provenance),len(rows),sha(out))
if __name__=='__main__':main()
