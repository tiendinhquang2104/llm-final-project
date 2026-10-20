"""Manually authored artificial TRAIN cases. Not validation/public examples.

Development and check cases have different statements, functions and structure,
not just renamed source. Expected findings are assistant-authored fixture oracle
annotations, never inference inputs and never certified by matching taxonomy.
"""
from dataclasses import dataclass
from src.task3.discovery import DiscoveryInput


@dataclass(frozen=True)
class Case:
    name: str
    exam: str
    group: str
    code: str
    statement: str
    expected: tuple
    problems: tuple = ()


def expectation(group,quote,fact,cause,proof,action=None,pid=None):
    return dict(taxonomy_group=group,quote=quote,observed_fact=fact,cause=cause,
                evidence={'fixture_oracle_proof':proof,'authority':'assistant_authored_artificial_train'},
                repair_action=action,problem_id=pid)


def development_cases():
    E=expectation
    return [
        Case('dev-exit','dev-status','dev-status','int main(){return 2;}','Program exit status must be 7.',
             (E('Lỗi logic','2','Trả trạng thái 2.','Đặc tả yêu cầu 7, khác 2.','entire return-constant program'),)),
        Case('dev-clean','dev-clean','dev-clean','int main(){return 0;}','Program exit status must be 0.',()),
        Case('dev-warning','dev-warning','dev-warning',"int main(){int v='ab';return 0;}",'Return zero; multichar literal is permitted.',()),
        Case('dev-literal','dev-file','dev-file','#include <fstream>\n#include <string>\nvoid load(std::string route){std::ifstream stream("route");}',
             'Read the file whose path is parameter route.',
             (E('Lỗi hard-code','std::ifstream stream("route")','Mở literal thay vì đường dẫn tham số.','Literal không dùng giá trị route.','formal string route plus explicit path specification',pid='Q1'),),
             ({'pid':'Q1','prototype':'void load(std::string route);'},)),
        Case('dev-loop','dev-loop','dev-loop','void scan(int cursor){unsigned total=0;while(cursor){total++;}}','scan must terminate for any cursor.',
             (E('Lỗi vòng lặp','while(cursor){total++;}','Không cập nhật điều kiện.','Nếu cursor khác 0, điều kiện bất biến và không có thao tác tiến triển quan sát được; C++11 không bảo đảm hành vi kết thúc.','unsigned increment defined, value parameter unchanged'),)),
        Case('dev-progress','dev-progress','dev-progress','void scan(int cursor){while(cursor){cursor--;}}','Input cursor is nonnegative; scan must terminate.',()),
        Case('dev-two','dev-two','dev-two','void scan(int cursor){unsigned total=0;while(cursor){total++;}}\nint main(){return missing;}',
             'scan must terminate for any cursor.',
             (E('Lỗi vòng lặp','while(cursor){total++;}','Điều kiện không đổi.','Nếu cursor khác 0, điều kiện bất biến và không có thao tác tiến triển quan sát được; C++11 không bảo đảm hành vi kết thúc.','same invariant proof'),
              E('Lỗi biên dịch','int main(){return missing;}','Tên missing không khai báo.','Compiler từ chối tên chưa khai báo.','fresh compiler error'))),
    ]


def independent_cases():
    E=expectation
    return [
        Case('check-compile','check-c','check-c',"int main(){char c='xy';return notHere;}",'The program must return zero.',
             (E('Lỗi biên dịch',"int main(){char c='xy';return notHere;}",'Compiler từ chối tên chưa khai báo.','Tên notHere chưa có khai báo.','fresh error separate from multichar warning'),)),
        Case('check-io','check-output','check-output','#include <iostream>\nint main(){std::cout<<"YES";}', 'Print exactly OK.',
             (E('Lỗi nhập/xuất','std::cout<<"YES"','In token YES.','Token YES khác token OK được yêu cầu.','entire unconditional output compared to specification'),)),
        Case('check-logic','check-status','check-status','int main( ){ return 11; }','Program exit status must be 9.',
             (E('Lỗi logic','11','Trả trạng thái 11.','Đặc tả yêu cầu 9.','entire bounded program'),)),
        Case('check-loop','check-iteration','check-iteration','void advance(int pending) { unsigned int seen = 5; while (pending) { seen ++; } }',
             'advance must return for every integer pending.',
             (E('Lỗi vòng lặp','while (pending) { seen ++; }','Điều kiện pending bất biến.','Với pending khác 0, điều kiện bất biến; vòng lặp không tạo tiến triển quan sát được theo yêu cầu C++11.','unsigned wrap and immutable value parameter'),)),
        Case('check-array','check-memory','check-memory','int main(){int data[2]={3,4};return data[2];}','Return the first array element.',
             (E('Lỗi mảng/chuỗi','data[2];','Truy cập index 2 trên mảng dài 2.','Index nằm ngoài miền 0..1.','declared array extent and constant subscript'),)),
        Case('check-function','check-return','check-return','int value(){}\nint main(){return value();}','value must return 4.',
             (E('Lỗi hàm','int value(){}','Hàm int không trả giá trị.','Luồng chạy đến cuối hàm non-void được gọi.','empty function body, actual call from main; warning not compile error'),)),
        Case('check-edge','check-zero','check-zero','int divide(int n){return 10/n;}','Return 0 for n=0, otherwise return integer quotient 10/n.',
             (E('Lỗi edge case','10/n','Phép chia không có nhánh n=0.','Input 0 hợp lệ gây chia cho 0.','specified zero input substituted into unconditional division'),)),
        Case('check-algorithm','check-formula','check-formula','int square(int n){return n+n;}','For 1 <= n <= 10, return n squared.',
             (E('Lỗi thuật toán','n+n','Hàm trả 2*n.','n=3 cho 6, khác bình phương 9.','bounded mathematical counterexample from statement'),)),
        Case('check-file','check-resource','check-resource','#include <fstream>\n#include <string>\nvoid ingest(std::string resource) { std::ifstream input("resource"); }',
             'Read the file whose path is parameter resource.',
             (E('Lỗi hard-code','std::ifstream input("resource")','Mở literal resource.','Không dùng đường dẫn resource được truyền vào.','formal string and explicit specification',pid='FILE'),),
             ({'pid':'FILE','prototype':'void ingest(std::string resource);'},)),
        Case('check-style','check-rule','check-rule','using namespace std;\nint main(){return 0;}','Return zero. Do not use a using-directive.',
             (E('Lỗi style','using namespace std;','Có using-directive.','Vi phạm điều cấm using-directive trong đề.','explicit style rule and directive'),)),
        Case('check-clean','check-correct','check-correct','int main(){return 6;}','Program exit status must be 6.',()),
        Case('check-warning','check-warnings','check-warnings',"int main(){long marker='cd';return 0;}",'Return zero; warning does not violate specification.',()),
        Case('check-literal-distractor','check-fixed','check-fixed','#include <fstream>\nvoid ingest(){std::ifstream input("resource");}',
             'Open the fixed file resource.',()),
        Case('check-combination','check-combo','check-combo','void count(int remaining){unsigned sum=8;while(remaining){sum++;}}\nint main(){return anotherMissing;}',
             'count must terminate for any remaining.',
             (E('Lỗi vòng lặp','while(remaining){sum++;}','Điều kiện không đổi.','Với remaining khác 0, vòng lặp không tạo tiến triển quan sát được; không có bảo đảm hành vi C++11.','unsigned increment, unchanged parameter'),
              E('Lỗi biên dịch','int main(){return anotherMissing;}','Tên chưa khai báo.','Compiler từ chối tên chưa khai báo.','fresh compiler diagnostic'))),
        Case('check-unsupported-repair','check-bound','check-bound','int sum(int n){int s=0;for(int i=0;i<=n;i++){s+=i;}return s;}',
             'For n from 1 to 8, sum integers strictly less than n.',
             (E('Lỗi edge case','i<=n','Vòng lặp cộng cả n.','n=1 trả 1 thay vì tổng rỗng 0.','boundary counterexample for independent unsupported repair'),)),
    ]


def oracle_findings(case):
    """Build source positions only; oracle facts above do not call the extractor."""
    result=[]
    for i,expected in enumerate(case.expected):
        f=dict(expected);quote=f.pop('quote');start=case.code.index(quote);end=start+len(quote)
        action=f['repair_action']
        if f['taxonomy_group']=='Lỗi hard-code':
            import re
            reference=re.search(r'parameter (\w+)',case.statement)[1];target='"'+reference+'"'
            a=case.code.index(target)
            action={'target':target,'reference':reference,'span_start':a,'span_end':a+len(target),
                    'replacement':reference,'text':f'Dùng giá trị tham số {reference} thay cho literal trong lời gọi mở file.'}
        if f['taxonomy_group']=='Lỗi logic' and case.statement.startswith('Program exit status'):
            import re
            required=re.search(r'(\d+)\.',case.statement)[1]
            action={'target':quote,'reference':required,'span_start':start,'span_end':end,
                    'replacement':required,'text':f'Đặt trạng thái trả về thành {required} theo đặc tả.'}
        result.append(dict(f,repair_action=action,finding_id=f'fixture-oracle-{i}',
            source_span={'start':start,'end':end,'quote':quote,'line_start':case.code[:start].count('\n')+1,
                         'line_end':case.code[:end].count('\n')+1},status='supported_error',confidence='fixture_oracle'))
    return result
