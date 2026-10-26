#!/usr/bin/env python3
"""Author synthetic final-only cases and privately verify with CppSandbox.

No model calls or public-feedback labels. Specification oracles are Python
implementations independent of the C++ solutions. This is agent-reviewed data,
not independent human gold. Training and checkpoint selection must not read it.
"""
from __future__ import annotations

import argparse
import csv
import functools
import hashlib
import io
import ipaddress
import itertools
import json
from pathlib import Path
import random
import re
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'data/raw/task3-sft-v2-authoring'
VERIFY = DEST / 'final-verification'
TEMPLATE = Path('/workspace/llm-final-project/outputs/task3/round23-20261022/sandbox-template')
HEADER = '#include <bits/stdc++.h>\nusing namespace std;\n'
FAMILIES = []


def add(key, title, specification, invariant, distinction, codes, mutations, diagnoses,
        repairs, clean_notes, inputs, checker='tokens', labels=None):
    FAMILIES.append(dict(key=key, title=title, statement=specification +
        '\nNộp chương trình C++11 đầy đủ có main. ' +
        ('Output phải khớp từng byte, gồm LF cuối mỗi dòng.' if checker == 'exact_bytes'
         else 'Output so theo token, phân biệt hoa thường.'), invariant=invariant,
        distinction=distinction, codes=[HEADER + c.strip() + '\n' for c in codes],
        mutations=mutations, diagnoses=diagnoses, repairs=repairs,
        clean_notes=clean_notes, inputs=inputs, checker=checker,
        labels=labels or [['Lỗi logic'], ['Lỗi logic']]))


add('csv', 'Giải mã bản ghi CSV có dấu nháy',
    'Đọc một dòng CSV hợp lệ dài tối đa 100 ký tự ASCII. Bản ghi có ít nhất một trường; '
    'dòng rỗng là một trường rỗng. Trường không đặt trong nháy chỉ chứa chữ cái và dấu cách. '
    'Trường đặt trong nháy kép có thể chứa thêm dấu phẩy; dấu nháy kép bên trong được viết thành hai dấu nháy kép liên tiếp. '
    'Các trường cách nhau bằng dấu phẩy; không có ký tự ngoài trường nháy trước dấu phẩy. '
    'In số trường ở dòng đầu; mỗi dòng sau in độ dài trường đã giải mã, dấu hai chấm, rồi nội dung trường.',
    'Dấu phẩy chỉ kết thúc trường khi ở ngoài nháy; hai dấu nháy trong trường tạo một ký tự nháy.',
    'Máy trạng thái CSV và giải thoát nháy kép, khác đếm từ theo whitespace của F08 và ngăn xếp ngoặc F13.',
    [r'''
int main(){
    string s; getline(cin,s); vector<string> fields; string field; bool quoted=false;
    for(size_t i=0;i<s.size();++i){
        if(s[i]=='"'){
            if(quoted && i+1<s.size() && s[i+1]=='"'){field += '"'; ++i;}
            else quoted=!quoted;
        } else if(s[i]==',' && !quoted){fields.push_back(field); field.clear();}
        else field+=s[i];
    }
    fields.push_back(field); cout<<fields.size()<<'\n';
    for(const string& f:fields) cout<<f.size()<<':'<<f<<'\n';
}''', r'''
int main(){
    string s; getline(cin,s); vector<string> values; size_t pos=0;
    for(;;){
        string out;
        if(pos<s.size() && s[pos]=='"'){
            ++pos;
            while(pos<s.size()){
                if(s[pos]!='"'){out+=s[pos++];}
                else if(pos+1<s.size() && s[pos+1]=='"'){out.push_back('"');pos+=2;}
                else {++pos;break;}
            }
        } else while(pos<s.size() && s[pos]!=',') out+=s[pos++];
        values.push_back(out);
        if(pos==s.size()) break;
        ++pos;
    }
    cout<<values.size()<<'\n';
    for(auto v:values)cout<<v.length()<<':'<<v<<'\n';
}'''],
    [('field += \'"\';', 'field += "";'), ("out.push_back('\"');", "out.push_back(',');")],
    ['Nhánh xử lý hai dấu nháy liên tiếp bỏ mất ký tự nháy trong nội dung trường.',
     'Nhánh giải thoát hai dấu nháy của vòng while chèn dấu phẩy vào nội dung trường.'],
    ['Trong nhánh hai dấu nháy liên tiếp, thêm một ký tự nháy kép vào field rồi mới bỏ qua ký tự thứ hai.',
     'Thay ký tự dấu phẩy được thêm bởi out.push_back trong nhánh nháy kép liên tiếp bằng một dấu nháy kép.'],
    ['Biến quoted tách dấu phẩy phân cách khỏi dấu phẩy trong trường; nhánh nháy kép liên tiếp giữ một nháy.',
     'Bộ phân tích đọc riêng trường có nháy và trường thường; cặp nháy được giải mã trước khi kết thúc trường.'],
    ['\n', ',\n', 'a,b\n', '"a,b",c\n', '"a""b"\n', '""\n', '""""\n',
     'a,,b,\n', '"a,b","c""d",\n', 'hello world," a "\n', '"x""y""z",a\n',
     '"""a""",b\n', ',"",\n', 'a'*100+'\n'], checker='exact_bytes',
    labels=[['Lỗi logic'], ['Lỗi logic']])

add('ipv4', 'Xác thực địa chỉ IPv4 dạng chuẩn',
    'Đọc một token không rỗng dài tối đa 40 ký tự, chỉ gồm chữ cái ASCII, chữ số, dấu chấm, dấu cộng hoặc dấu trừ. '
    'In YES khi token gồm đúng bốn thành phần thập phân cách bởi dấu chấm, mỗi thành phần trong [0,255], '
    'chỉ gồm chữ số và không có số 0 đứng đầu trừ thành phần "0". Các trường hợp khác in NO.',
    'Mỗi thành phần có giới hạn riêng và cú pháp chuẩn; cả số lượng thành phần lẫn dấu phân cách đều phải hợp lệ.',
    'Xác thực cấu trúc địa chỉ nhiều thành phần, không phải phép đếm hay tìm kiếm trên dãy của bộ cũ.',
    [r'''
int main(){
    string s,part;cin>>s; stringstream stream(s); int count=0; bool ok=s.back()!='.';
    while(getline(stream,part,'.')){
        ++count; bool local=!part.empty() && part.size()<=3;
        int value=0;
        for(char c:part){if(c<'0'||c>'9')local=false;else if(part.size()<=3)value=value*10+c-'0';}
        if(part.size()>1 && part[0]=='0') local=false;
        if(!(value<=255))local=false;
        ok=ok&&local;
    }
    cout<<(ok && count==4?"YES":"NO")<<'\n';
}''', r'''
int main(){
    string s;cin>>s; s+='.';int value=0,len=0,parts=0;bool leading=false,valid=true;
    for(char c:s){
        if(c=='.'){
            if(len==0||len>3||value>255||(leading && len>1))valid=false;
            ++parts;value=0;len=0;leading=false;
        } else if(c>='0' && c<='9'){
            if(len==0)leading=c=='0'; ++len;
            if(len<=3)value=value*10+c-'0';
        } else valid=false;
    }
    cout<<(valid && parts==4?"YES":"NO")<<'\n';
}'''],
    [('value<=255', 'value<=256'), ('leading && len>1', 'leading && len>2')],
    ['Điều kiện kiểm tra value cho phép thành phần 256 vượt giới hạn địa chỉ IPv4.',
     'Điều kiện leading ở dấu chấm chấp nhận thành phần hai chữ số có số không đứng đầu.'],
    ['Đặt giới hạn trên của value trong kiểm tra từng thành phần về 255.',
     'Khi leading đúng, loại mọi thành phần có độ dài lớn hơn một, kể cả độ dài hai.'],
    ['Tách theo dấu chấm đồng thời kiểm tra thành phần rỗng, chữ số, số không đầu và giới hạn giá trị.',
     'Trạng thái value, len và leading được đặt lại ở mỗi dấu chấm; dấu chấm thêm cuối giúp kiểm tra cả thành phần cuối.'],
    [s+'\n' for s in ['0.0.0.0','255.255.255.255','256.1.2.3','1.2.3.256','01.2.3.4','1.2.03.4',
     '1.2.3.4','1.2.3','1.2.3.4.5','1..2.3','.1.2.3','1.2.3.','+1.2.3.4','-1.2.3.4',
     'a.2.3.4','000.0.0.0','9999.1.1.1','10.20.30.40','00.0.0.0','9'*40]])

add('rook', 'Các ô xe có thể tới khi bị chắn',
    'Đọc bàn cờ 8 hàng, mỗi hàng 8 ký tự thuộc {.,#,R}, có đúng một R. R là quân xe; # là ô bị chiếm. '
    'Xe đi ngang hoặc dọc qua các ô trống ., không được đi qua hay đến ô #. In số ô trống có thể tới trong một nước.',
    'Trên mỗi tia ngang hoặc dọc, chỉ các ô trống đứng trước vật cản đầu tiên được tính.',
    'Tầm nhìn theo tia với vật cản, khác khoảng cách Manhattan F03 và tìm đường BFS F45.',
    [r'''
int main(){
    vector<string>b(8);int r=0,c=0;
    for(int i=0;i<8;++i){cin>>b[i];for(int j=0;j<8;++j)if(b[i][j]=='R'){r=i;c=j;}}
    int dr[4]={1,-1,0,0},dc[4]={0,0,1,-1},answer=0;
    for(int d=0;d<4;++d)for(int step=1;step<8;++step){
        int x=r+dr[d]*step,y=c+dc[d]*step;
        if(x<0||x>=8||y<0||y>=8)break;
        if(b[x][y]=='#')break;
        ++answer;
    }
    cout<<answer<<'\n';
}''', r'''
int main(){
    string board[8];int rr=0,cc=0;
    for(int i=0;i<8;++i){cin>>board[i];for(int j=0;j<8;++j)if(board[i][j]=='R'){rr=i;cc=j;}}
    int total=0;
    for(int x=0;x<8;++x)for(int y=0;y<8;++y){
        if(board[x][y]!='.' || (x!=rr && y!=cc))continue;
        int distance=abs(x-rr)+abs(y-cc),dx=(x>rr)-(x<rr),dy=(y>cc)-(y<cc);bool clear=true;
        for(int k=1;k<distance;++k)if(board[rr+k*dx][cc+k*dy]=='#')clear=false;
        if(clear)++total;
    }
    cout<<total<<'\n';
}'''],
    [("if(b[x][y]=='#')break;", "if(b[x][y]=='#')continue;"),
     ('for(int k=1;k<distance;++k)', 'for(int k=2;k<distance;++k)')],
    ['Nhánh gặp # của vòng duyệt tia tiếp tục xét các ô phía sau vật cản.',
     'Vòng kiểm tra đường đi bắt đầu ở k bằng hai nên bỏ qua ô sát quân xe.'],
    ['Khi gặp #, kết thúc vòng duyệt tia hiện tại bằng break để không tính các ô phía sau.',
     'Cho vòng kiểm tra vật cản bắt đầu từ k bằng một để xét cả ô liền kề quân xe.'],
    ['Mỗi hướng dừng tại biên bàn hoặc vật cản đầu tiên; ô R không được cộng vào kết quả.',
     'Mỗi ô đích cùng hàng hoặc cột chỉ được đếm nếu toàn bộ ô nằm giữa nó và xe đều trống.'],
    [], labels=[['Lỗi vòng lặp'], ['Lỗi vòng lặp']])

add('rotate', 'Xoay vòng bit trong độ rộng cố định',
    'Đọc w, k, x với 1<=w<=16, 0<=k<=100, 0<=x<2^w. Xem x là chuỗi nhị phân đúng w bit, '
    'kể cả các bit 0 đầu. Xoay vòng chuỗi sang trái k vị trí và in giá trị thập phân của chuỗi kết quả.',
    'Chỉ k modulo w tác động đến kết quả; các bit rời đầu trái quay lại cuối phải trong đúng w bit.',
    'Hoán vị vòng các bit độ rộng cố định; không dùng lại đảo chữ số thập phân F22.',
    [r'''
int main(){
    unsigned w,k,x;cin>>w>>k>>x;k%=w;unsigned mask=(1u<<w)-1;
    unsigned answer=((x<<k)|(x>>(w-k)))&mask;
    cout<<answer<<'\n';
}''', r'''
int main(){
    int w,k,x;cin>>w>>k>>x; string bits;
    for(int i=w-1;i>=0;--i)bits+=char('0'+((x>>i)&1));
    k=k%w;
    string moved=bits.substr(k)+bits.substr(0,k); int value=0;
    for(char bit:moved)value=value*2+(bit-'0');
    cout<<value<<'\n';
}'''],
    [('((x<<k)|(x>>(w-k)))', '((x<<k)&(x>>(w-k)))'), ('k=k%w;', 'k=(k%w+1)%w;')],
    ['Biểu thức ghép hai phần bit dùng phép AND nên làm mất các bit cần quay vòng.',
     'Phép chuẩn hóa k cộng thêm một nên số vị trí xoay khác đầu vào yêu cầu.'],
    ['Ghép phần dịch trái và phần quay lại bằng phép OR, rồi giữ mặt nạ w bit.',
     'Chuẩn hóa k chỉ bằng k modulo w, bỏ phần cộng thêm một trước khi cắt chuỗi bit.'],
    ['Hai phép dịch ghép phần còn lại với phần quay về, còn mask giữ đúng w bit; k bằng không vẫn hợp lệ.',
     'Chuỗi bits chứa đủ w bit kể cả số không đầu; cắt tại k modulo w thực hiện đúng phép xoay trái.'],
    [f'{w} {k} {x}\n' for w,k,x in [(1,0,0),(1,100,1),(4,1,9),(4,0,9),(4,4,9),(4,5,9),
     (16,100,65535),(16,15,1),(16,1,32768),(8,3,0),(8,3,129),(5,2,19),(2,1,1),(16,0,42)]])

add('floor', 'Thương nguyên làm tròn xuống',
    'Đọc hai số nguyên a,b với -1000<=a<=1000, -30<=b<=30 và b khác 0. '
    'In floor(a/b), tức số nguyên lớn nhất không vượt thương toán học, kể cả khi thương âm.',
    'Phép chia C++ làm tròn về không; thương âm có dư cần được chuyển về phía âm vô cùng.',
    'Quy tắc làm tròn phép chia có dấu, khác UCLN và chuẩn hóa phân số của G16.',
    [r'''
int main(){
    int a,b;cin>>a>>b;int q=a/b,r=a%b;
    if(r!=0 && ((a<0)!=(b<0)))--q;
    cout<<q<<'\n';
}''', r'''
int main(){
    int a,b;cin>>a>>b;int A=abs(a),B=abs(b),result;
    if((a<0)==(b<0))result=A/B;
    else result=-(A+B-1)/B;
    cout<<result<<'\n';
}'''],
    [(')))--q;', ')))++q;'), ('result=-(A+B-1)/B;', 'result=-A/B;')],
    ['Nhánh thương âm có dư tăng q nên đi ngược hướng làm tròn xuống.',
     'Nhánh a và b trái dấu dùng -A/B nên làm tròn thương âm có dư về không.'],
    ['Ở nhánh có dư và trái dấu, giảm q một đơn vị thay vì tăng.',
     'Tính độ lớn thương âm bằng (A+B-1)/B rồi đổi dấu để làm tròn xuống khi có dư.'],
    ['Điều kiện có dư và khác dấu chọn đúng các thương cần giảm thêm; trường hợp chia hết giữ nguyên q.',
     'Nhánh cùng dấu chia độ lớn trực tiếp; nhánh trái dấu lấy đối của thương độ lớn làm tròn lên.'],
    [f'{a} {b}\n' for a,b in [(-7,3),(7,-3),(-7,-3),(7,3),(0,1),(0,-30),(-9,3),(9,-3),
     (-1,30),(1,-30),(-1000,30),(1000,-30),(1000,1),(-1000,-1),(3,30)]])

add('permutation', 'Hoán vị kế tiếp theo thứ tự từ điển',
    'Đọc n (1<=n<=7), rồi n số nguyên trong [0,3], có thể trùng. In dãy nhỏ nhất theo thứ tự từ điển '
    'lớn hơn dãy đầu vào và có cùng đa tập phần tử. Nếu không tồn tại, in dãy nhỏ nhất của đa tập đó.',
    'Giữ tiền tố dài nhất có thể, tăng vị trí chốt nhỏ nhất có thể và đưa hậu tố về thứ tự tăng.',
    'Chuyển trạng thái hoán vị từ điển, không phải chỉ sắp xếp hoặc loại trùng như F30/F31.',
    [r'''
int main(){
    int n;cin>>n;vector<int>a(n);for(int&x:a)cin>>x;
    next_permutation(a.begin(),a.end());
    for(int x:a)cout<<x<<' ';cout<<'\n';
}''', r'''
int main(){
    int n;cin>>n;vector<int>a(n);for(int&x:a)cin>>x;
    int i=n-2;while(i>=0 && a[i]>=a[i+1])--i;
    if(i>=0){int j=n-1;while(a[j]<=a[i])--j;swap(a[i],a[j]);}
    reverse(a.begin()+i+1,a.end());
    for(int x:a)cout<<x<<' ';cout<<'\n';
}'''],
    [('next_permutation(a.begin(),a.end());', 'prev_permutation(a.begin(),a.end());'),
     ('while(a[j]<=a[i])', 'while(a[j]<a[i])')],
    ['Lời gọi prev_permutation tìm dãy đứng trước thay vì dãy kế tiếp theo thứ tự từ điển.',
     'Điều kiện tìm j cho phép chọn phần tử bằng vị trí chốt nên có thể không tăng được dãy.'],
    ['Dùng next_permutation để tìm hoán vị kế tiếp và tự quay về dãy nhỏ nhất khi đã ở cuối.',
     'Bỏ qua cả phần tử bằng chốt khi tìm j, tức chỉ đổi chốt với phần tử lớn hơn nó.'],
    ['next_permutation xử lý cả phần tử trùng và tự đưa dãy cuối về thứ tự nhỏ nhất.',
     'Vị trí chốt đứng trước hậu tố không tăng; đổi với phần tử lớn hơn rồi đảo hậu tố tạo dãy kế tiếp nhỏ nhất.'],
    ['1\n0\n','3\n1 2 1\n','3\n0 1 2\n','3\n2 1 0\n','3\n1 1 1\n',
     '4\n1 3 2 2\n','4\n0 0 1 1\n','7\n3 3 2 2 1 1 0\n',
     '5\n0 3 1 1 1\n','2\n1 0\n','2\n0 1\n'], labels=[['Lỗi thuật toán'], ['Lỗi logic']])

add('glob', 'Khớp toàn bộ chuỗi với wildcard',
    'Đọc hai dòng: dòng đầu là chuỗi s chỉ gồm a,b dài 0..10; dòng sau là mẫu p chỉ gồm a,b,?,* dài 0..10. '
    'Dấu ? khớp đúng một ký tự, dấu * khớp một dãy bất kỳ kể cả rỗng; a,b khớp chính nó. '
    'In YES nếu mẫu khớp toàn bộ s, ngược lại NO.',
    'Trạng thái là hai tiền tố hay hai hậu tố của chuỗi và mẫu; dấu sao có nhánh rỗng và nhánh tiêu thụ ký tự.',
    'Nhận dạng ngôn ngữ mẫu hai chiều, khác stack biểu thức F44 và DP chọn món/đổi tiền G47.',
    [r'''
int main(){
    string s,p;getline(cin,s);getline(cin,p);int n=s.size(),m=p.size();
    bool dp[11][11]={};dp[0][0]=true;
    for(int i=0;i<=n;++i)for(int j=1;j<=m;++j){
        if(p[j-1]=='*')dp[i][j]=dp[i][j-1]||(i>0 && dp[i-1][j]);
        else if(i>0)dp[i][j]=(p[j-1]=='?'||p[j-1]==s[i-1])&&dp[i-1][j-1];
    }
    cout<<(dp[n][m]?"YES":"NO")<<'\n';
}''', r'''
string s,p;int memo[11][11];
bool go(int i,int j){
    if(j==(int)p.size())return i==(int)s.size();
    int &r=memo[i][j];if(r!=-1)return r;
    if(p[j]=='*')return r=(go(i,j+1)||(i<(int)s.size() && go(i+1,j)));
    return r=(i<(int)s.size() && (p[j]=='?'||p[j]==s[i]) && go(i+1,j+1));
}
int main(){getline(cin,s);getline(cin,p);memset(memo,-1,sizeof(memo));cout<<(go(0,0)?"YES":"NO")<<'\n';}
'''],
    [('dp[i][j-1]||(i>0 && dp[i-1][j])', 'false||(i>0 && dp[i-1][j])'),
     ('i<(int)s.size() && go(i+1,j)', 'i<(int)s.size() && go(i+1,j+1)')],
    ['Công thức DP cho dấu sao bỏ nhánh khớp rỗng nên không thể bỏ qua dấu sao.',
     'Nhánh dấu sao tiêu thụ ký tự đồng thời tăng j nên sao không thể khớp nhiều ký tự.'],
    ['Khôi phục nhánh dp[i][j-1] cho dấu sao khớp rỗng, cùng nhánh giữ sao để tiêu thụ ký tự.',
     'Ở nhánh tiêu thụ của dấu sao, tăng i nhưng giữ nguyên j để sao có thể khớp tiếp nhiều ký tự.'],
    ['DP có trạng thái tiền tố rỗng và hai nhánh đúng cho dấu sao; ký tự thường và ? cùng tiêu thụ một ký tự.',
     'Đệ quy ghi nhớ xử lý hai hậu tố; dấu sao hoặc bỏ qua chính nó hoặc tiêu thụ một ký tự mà vẫn giữ sao.'],
    [s+'\n'+p+'\n' for s,p in [('', ''),('', '*'),('', '**'),('', '?'),('ab','a*'),('ab','*'),
     ('aaa','a*'),('ab','?b'),('aba','a?a'),('ab','a'),('a','a*'),('aaab','a*b'),
     ('ab','*a'),('ababababab','*b'),('b','a*'),('a','**?**'),('ab','*?*?*')]],
    labels=[['Lỗi thuật toán'], ['Lỗi thuật toán']])

add('mines', 'Điền số hàng xóm của bãi mìn',
    'Đọc r,c (1<=r,c<=6), rồi r hàng c ký tự . hoặc *. Mỗi * là một quả mìn. '
    'In r hàng: giữ nguyên *; thay mỗi . bằng chữ số số mìn trong tối đa tám ô kề cạnh hoặc kề góc. '
    'Ngoài biên không có ô; không tính chính ô đang xét.',
    'Mỗi ô trống nhận đúng số mìn tại các độ lệch hàng và cột trong [-1,1], trừ độ lệch (0,0).',
    'Stencil tám hàng xóm, khác phép chuyển vị/xoay ma trận G14 và tổng hàng G01.',
    [r'''
int main(){
    int r,c;cin>>r>>c;vector<string>a(r);for(auto&row:a)cin>>row;
    for(int i=0;i<r;++i){for(int j=0;j<c;++j){
        if(a[i][j]=='*'){cout<<'*';continue;}int count=0;
        for(int dr=-1;dr<=1;++dr)for(int dc=-1;dc<=1;++dc){
            if(dr==0 && dc==0)continue;
            int x=i+dr,y=j+dc;if(x>=0&&x<r&&y>=0&&y<c&&a[x][y]=='*')++count;
        }
        cout<<count;
    }cout<<'\n';}
}''', r'''
int main(){
    int r,c;cin>>r>>c;vector<string>b(r);for(string&row:b)cin>>row;int count[6][6]={};
    for(int i=0;i<r;++i)for(int j=0;j<c;++j)if(b[i][j]=='*'){
        for(int x=i-1;x<=i+1;++x)for(int y=j-1;y<=j+1;++y){
            if(x==i && y==j)continue;
            if(x>=0 && x<r && y>=0 && y<c)++count[x][y];
        }
    }
    for(int i=0;i<r;++i){for(int j=0;j<c;++j)cout<<(b[i][j]=='*'?'*':char('0'+count[i][j]));cout<<'\n';}
}'''],
    [('if(dr==0 && dc==0)', 'if(dr==0 || dc==0)'), ('++count[x][y];', 'count[x][y]=1;')],
    ['Điều kiện bỏ qua độ lệch dùng OR nên bỏ cả các hàng xóm chung hàng hoặc chung cột.',
     'Vòng phát tán từ mìn gán count bằng một nên mất đóng góp khi một ô kề nhiều mìn.'],
    ['Chỉ bỏ độ lệch khi cả dr và dc đều bằng không bằng điều kiện AND.',
     'Tăng count[x][y] thêm một cho mỗi quả mìn kề thay vì gán lại bằng một.'],
    ['Mỗi ô trống duyệt đủ tám độ lệch, loại chính nó và kiểm tra biên trước khi đọc ô kề.',
     'Mỗi quả mìn cộng một vào mọi ô hàng xóm hợp lệ; lúc xuất chỉ ô trống mới dùng bảng count.'],
    ['1 1\n.\n','1 1\n*\n','1 3\n*.*\n','3 1\n*\n.\n*\n','2 2\n*.\n.*\n',
     '3 3\n***\n*.*\n***\n','2 3\n...\n...\n','3 3\n...\n.*.\n...\n'], checker='exact_bytes')

add('merge', 'Chi phí gộp đống tối thiểu',
    'Đọc n (0<=n<=7), rồi n trọng lượng nguyên trong [0,20]. Mỗi bước chọn hai đống bất kỳ, '
    'gộp thành một đống có trọng lượng bằng tổng hai đống và trả chi phí bằng tổng đó. '
    'Lặp tới khi còn tối đa một đống; in tổng chi phí nhỏ nhất có thể. n bằng 0 hoặc 1 cho chi phí 0.',
    'Mỗi bước gộp hai trọng lượng nhỏ nhất và cộng chi phí bước đó vào chi phí tích lũy.',
    'Thuật toán tham lam hàng đợi ưu tiên cho cây gộp tối ưu, khác gộp dãy đã sắp F33 và gộp đoạn F49.',
    [r'''
int main(){
    int n;cin>>n;priority_queue<int,vector<int>,greater<int>> q;
    for(int i=0,x;i<n;++i){cin>>x;q.push(x);}int cost=0;
    while(q.size()>1){int x=q.top();q.pop();int y=q.top();q.pop();int sum=x+y;cost+=sum;q.push(sum);}
    cout<<cost<<'\n';
}''', r'''
int main(){
    int n;cin>>n;multiset<int> piles;for(int i=0,x;i<n;++i){cin>>x;piles.insert(x);}int cost=0;
    while(piles.size()>1){
        auto it=piles.begin();int left=*it;piles.erase(it);
        it=piles.begin();int right=*it;piles.erase(it);
        cost+=left+right;piles.insert(left+right);
    }
    cout<<cost<<'\n';
}'''],
    [('greater<int>> q;', 'less<int>> q;'), ('cost+=left+right;', 'cost=left+right;')],
    ['Bộ so sánh less của priority_queue chọn hai đống lớn nhất nên không bảo đảm chi phí gộp nhỏ nhất.',
     'Phép gán cost trong vòng gộp xóa chi phí các bước trước và chỉ giữ chi phí bước cuối.'],
    ['Dùng bộ so sánh greater<int> cho priority_queue để lấy ra hai trọng lượng nhỏ nhất mỗi bước.',
     'Cộng left+right vào cost bằng += để giữ tổng chi phí của mọi lần gộp.'],
    ['Min-heap lấy hai đống nhỏ nhất rồi đưa tổng của chúng trở lại; cost tích lũy đúng chi phí từng bước.',
     'multiset cho phép lấy hai phần tử nhỏ nhất kể cả khi trùng; tổng mới được chèn lại và chi phí được cộng dồn.'],
    ['0\n\n','1\n20\n','2\n3 7\n','3\n1 2 3\n','4\n1 1 1 1\n',
     '3\n0 0 5\n','5\n2 4 6 8 10\n','7\n20 20 20 20 20 20 20\n',
     '7\n0 0 0 0 0 0 0\n','4\n1 2 3 20\n'], labels=[['Lỗi thuật toán'], ['Lỗi logic']])

add('power', 'Lũy thừa modulo với số mũ lớn',
    'Đọc a,n,m với 0<=a<=1000, 0<=n<=1000000000 và 1<=m<=1000. '
    'In a^n modulo m; quy ước a^0=1 kể cả a=0. Cần dùng số phép toán tăng theo log(n+1).',
    'Bình phương cơ số và chia đôi số mũ giữ tích lũy tương đương lũy thừa ban đầu modulo m.',
    'Phân rã số mũ nhị phân, khác nhân liên tiếp giai thừa F19 và nâng từng chữ số với số mũ ngắn F06.',
    [r'''
int main(){
    long long a,n,m;cin>>a>>n>>m;long long result=1%m;a%=m;
    while(n){if(n&1)result=result*a%m;a=a*a%m;n/=2;}
    cout<<result<<'\n';
}''', r'''
long long power(long long a,long long n,long long m){
    if(n==0)return 1%m;
    long long h=power(a,n/2,m),value=h*h%m;
    if(n%2)value=value*a%m;
    return value;
}
int main(){long long a,n,m;cin>>a>>n>>m;cout<<power(a%m,n,m)<<'\n';}
'''],
    [('a=a*a%m;', 'a=a%m;'), ('if(n%2)', 'if(n%2==0)')],
    ['Vòng lặp chỉ lấy dư cơ số thay vì bình phương nó nên các bit số mũ dùng sai lũy thừa.',
     'Điều kiện n%2==0 nhân thêm cơ số cho số mũ chẵn và bỏ phép nhân cần thiết khi số mũ lẻ.'],
    ['Sau mỗi bit số mũ, cập nhật a bằng a*a modulo m trước khi chia đôi n.',
     'Chỉ nhân thêm a khi n lẻ; giữ kết quả h*h modulo m khi n chẵn.'],
    ['Vòng lặp dùng từng bit của n, bình phương a ở mỗi lượt và khởi tạo 1 modulo m để xử lý cả n bằng không.',
     'Đệ quy tính lũy thừa với số mũ chia đôi, bình phương kết quả rồi chỉ nhân thêm cơ số khi số mũ lẻ.'],
    [f'{a} {n} {m}\n' for a,n,m in [(0,0,1),(0,0,7),(0,100,11),(2,2,1000),(3,5,97),
     (7,1,13),(5,0,9),(1000,1000000000,997),(2,1000000000,1000),(999,999999999,1000),
     (17,64,101),(1,1000000000,1000),(1000,1,1),(5,6,7)]])


def augment_inputs():
    rng = random.Random(620261026)
    by_key = {f['key']: f for f in FAMILIES}
    boards = []
    for rr, cc, blockers in [(0,0,[]),(3,3,[(3,4)]),(3,3,[(2,3),(4,3),(3,2),(3,4)]),
                              (7,7,[(7,6),(6,7)]),(3,3,[(3,6),(1,3)])]:
        b = [['.']*8 for _ in range(8)]
        for r,c in blockers:b[r][c]='#'
        b[rr][cc]='R';boards.append('\n'.join(''.join(row) for row in b)+'\n')
    for _ in range(10):
        b=[['#' if rng.random()<.22 else '.' for _ in range(8)] for _ in range(8)]
        b[rng.randrange(8)][rng.randrange(8)]='R'
        boards.append('\n'.join(''.join(row) for row in b)+'\n')
    by_key['rook']['inputs'] = boards
    for _ in range(10):
        r,c=rng.randint(1,6),rng.randint(1,6)
        by_key['mines']['inputs'].append(f'{r} {c}\n'+'\n'.join(
            ''.join('*' if rng.random()<.4 else '.' for _ in range(c)) for _ in range(r))+'\n')
        w=rng.randint(1,16)
        by_key['rotate']['inputs'].append(f'{w} {rng.randint(0,100)} {rng.randrange(1<<w)}\n')
        a,b=rng.randint(-1000,1000),rng.choice([i for i in range(-30,31) if i])
        by_key['floor']['inputs'].append(f'{a} {b}\n')
        s=''.join(rng.choice('ab') for _ in range(rng.randint(0,10)))
        p=''.join(rng.choice('ab?*') for _ in range(rng.randint(0,10)))
        by_key['glob']['inputs'].append(s+'\n'+p+'\n')
        n=rng.randint(1,7);a=[rng.randrange(4) for _ in range(n)]
        by_key['permutation']['inputs'].append(str(n)+'\n'+' '.join(map(str,a))+'\n')
    for f in FAMILIES:f['inputs']=list(dict.fromkeys(f['inputs']))


augment_inputs()


@functools.lru_cache(maxsize=None)
def minimum_merge(state):
    if len(state)<2:return 0
    return min(state[i]+state[j]+minimum_merge(tuple(sorted(
        [v for k,v in enumerate(state) if k not in (i,j)]+[state[i]+state[j]])))
        for i in range(len(state)) for j in range(i+1,len(state)))


def oracle(key, text):
    """Compute expected outputs from the statement, never by executing a repair."""
    if key=='csv':
        s=text.rstrip('\n'); fields=[''] if s=='' else next(csv.reader([s],strict=True))
        return str(len(fields))+'\n'+''.join(f'{len(v)}:{v}\n' for v in fields)
    if key=='ipv4':
        try:ipaddress.IPv4Address(text.strip());valid=True
        except ipaddress.AddressValueError:valid=False
        return ('YES' if valid else 'NO')+'\n'
    if key=='rook':
        b=text.splitlines();rr,cc=next((r,c) for r in range(8) for c in range(8) if b[r][c]=='R')
        targets=[]
        for r in range(8):
            for c in range(8):
                if b[r][c]!='.' or (r!=rr and c!=cc):continue
                between=([b[x][c] for x in range(min(r,rr)+1,max(r,rr))] if c==cc else
                         [b[r][y] for y in range(min(c,cc)+1,max(c,cc))])
                if '#' not in between:targets.append((r,c))
        return str(len(targets))+'\n'
    if key=='rotate':
        w,k,x=map(int,text.split());bits=format(x,f'0{w}b');k%=w
        return str(int(bits[k:]+bits[:k],2))+'\n'
    if key=='floor':
        a,b=map(int,text.split());return str(a//b)+'\n'
    if key=='permutation':
        values=list(map(int,text.split()))[1:];order=sorted(set(itertools.permutations(values)))
        result=order[(order.index(tuple(values))+1)%len(order)]
        return ' '.join(map(str,result))+'\n'
    if key=='glob':
        s,p=text.splitlines();pattern=''.join('.*' if c=='*' else '.' if c=='?' else re.escape(c) for c in p)
        return ('YES' if re.fullmatch(pattern,s) else 'NO')+'\n'
    if key=='mines':
        lines=text.splitlines();r,c=map(int,lines[0].split());b=lines[1:]
        mines={(i,j) for i in range(r) for j in range(c) if b[i][j]=='*'}
        return ''.join(''.join('*' if (i,j) in mines else str(sum(
            max(abs(i-x),abs(j-y))==1 for x,y in mines)) for j in range(c))+'\n' for i in range(r))
    if key=='merge':return str(minimum_merge(tuple(sorted(map(int,text.split()[1:])))))+'\n'
    if key=='power':
        a,n,m=map(int,text.split());return str(pow(a,n,m))+'\n'
    raise KeyError(key)


def build_cases():
    cases=[]
    for index,f in enumerate(FAMILIES,1):
        family=f'V2E{index:02}'
        tests=[dict(input=s,expected=oracle(f['key'],s)) for s in f['inputs']]
        for pair in (1,2):
            clean=f['codes'][pair-1];before,after=f['mutations'][pair-1]
            assert clean.count(before)==1,(family,pair,before)
            clean_id=f'{family}-C{pair}'
            for defective in (False,True):
                sid=f'{family}-{"D" if defective else "C"}{pair}'
                labels=f['labels'][pair-1] if defective else []
                diagnosis=f['diagnoses'][pair-1] if defective else f['clean_notes'][pair-1]
                guidance=f['repairs'][pair-1] if defective else f['invariant']
                l4=(diagnosis+' '+guidance+' Chương trình đầy đủ sau đáp ứng yêu cầu.' if defective else
                    'Bài làm đáp ứng yêu cầu. '+diagnosis+' '+f['invariant']+' Có thể giữ nguyên chương trình sau.')
                targets={
                    '1':dict(taxonomy_error=labels,feedback='Bài làm còn lỗi theo yêu cầu đề.' if defective else 'Bài làm đáp ứng yêu cầu đề.'),
                    '2':dict(taxonomy_error=labels,feedback=diagnosis),
                    '3':dict(taxonomy_error=labels,feedback=diagnosis+' '+guidance),
                    '4':dict(taxonomy_error=labels,feedback=l4+'\n\n```cpp\n'+clean+'```')}
                cases.append(dict(sample_id=sid,pair_id=f'{family}-P{pair}',family_id=family,cluster=family,
                    split='final',title=f['title'],statement=f['statement'],exam_type='single_problem',
                    checker=f['checker'],code=clean.replace(before,after,1) if defective else clean,
                    harness='',labels=labels,intended_defective=defective,
                    expected_failure_kind='wrong_answer' if defective else 'none',solution_source_id=clean_id,
                    mechanism=diagnosis if defective else f['invariant'],
                    mutation=dict(before=before,after=after,reason=diagnosis) if defective else
                        dict(before='',after='',reason='Bản đúng được viết riêng, không biến đổi từ dữ liệu công khai.'),
                    invariant=f['invariant'],targets=targets,tests=tests,oracle_key=f['key'],
                    oracle_provenance='Authored synthetic; independent Python specification oracle in '
                        'scripts/task3_sft_v2_author_final.py:oracle; agent-reviewed, no independent human gold.',
                    annotation_origin='synthetic_agent_authored_and_verified',independent_human_review=False,
                    structural_distinction=f['distinction']))
    return cases


def extract_l4(case):
    return re.search(r'```cpp\n(.*?)```',case['targets']['4']['feedback'],re.S).group(1)


def validate_cases(cases):
    assert len(cases)==40 and sum(c['intended_defective'] for c in cases)==20
    assert len({c['sample_id'] for c in cases})==40
    official=json.loads((ROOT/'data/raw/task3-sft-v1/label_space.json').read_text())['taxonomy_error']
    ids={c['sample_id']:c for c in cases}
    assert len({c['code'] for c in cases})==40
    for c in cases:
        assert c['split']=='final' and c['family_id']==c['cluster']
        assert c['tests'] and c['targets'].keys()=={'1','2','3','4'}
        assert set(c['labels'])<=set(official)
        clean=ids[c['solution_source_id']]
        assert not clean['intended_defective'] and clean['pair_id']==c['pair_id']
        assert extract_l4(c)==clean['code']
        for target in c['targets'].values():
            assert target['taxonomy_error']==c['labels'] and target['feedback']
        assert all(t['expected']==oracle(c['oracle_key'],t['input']) for t in c['tests'])


def digest(value):return hashlib.sha256(value.encode() if isinstance(value,str) else value).hexdigest()


def dump(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


def author_review(cases, evidence, output):
    """Persist this author's source-grounded review, without claiming independence."""
    reviews=[]
    for c in cases:
        ev=evidence[c['sample_id']]
        witness=ev['witness']
        reviews.append(dict(sample_id=c['sample_id'],reviewer='author_agent',
            independent_review=False,source_sha256=ev['source_sha256'],
            specification_evidence=c['statement'],invariant=c['invariant'],
            observed_witness=(dict(test_index=witness['test_index'],input=witness['input'],
                expected=witness['expected'],actual=witness['stdout'],failure_kind=witness['failure_kind'])
                if witness and 'test_index' in witness else None),
            diagnosis_evidence=c['mechanism'],
            single_change_evidence=c['mutation'],
            verified_repair_source_id=c['solution_source_id'],
            repair_test_count=ev['repair_test_count'],
            level_reviews={
                '1':dict(verdict='pass',evidence='Status only; no source location, cause, or repair.'),
                '2':dict(verdict='pass',evidence='One sentence describes the actual source condition; no repair is prescribed.' if c['intended_defective'] else 'Explains the source behavior that satisfies the specification.'),
                '3':dict(verdict='pass',evidence=c['targets']['3']['feedback']),
                '4':dict(verdict='pass',explanation_evidence=c['invariant'],
                         complete_solution_source_sha256=ev['l4_source_sha256'],
                         bounded_execution_verified=ev['l4_verified_by_clean_partner'])},
            limitation='Self-review by authoring agent, supported by execution; no independent human annotation.'))
    dump(output/'author-review.private.json',reviews)
    old=json.loads((ROOT/'data/raw/task3-sft-v1/cases.private.json').read_text())
    old_sources={c['sample_id']:(ROOT/'data/raw/task3-sft-v1'/c['code_file']).read_text() for c in old}
    norm=lambda s:re.sub(r'\s+','',s)
    collisions=[]
    for c in cases:
        for sid,code in old_sources.items():
            if c['code']==code or norm(c['code'])==norm(code):
                collisions.append(dict(new_source=c['sample_id'],old_source=sid))
    dump(output/'v1-overlap.json',dict(passed=not collisions,new_sources=len(cases),old_sources=len(old_sources),
        modes=['exact_source','whitespace_removed'],collisions=collisions,
        structural_review=[dict(family_id=f'V2E{i:02}',distinction=f['distinction']) for i,f in enumerate(FAMILIES,1)],
        limitations='Exact and whitespace checks do not establish semantic independence; root runs broader public and structural checks before freezing.'))
    assert not collisions
    dump(output/'authored-checksums.json',dict(cases_sha256=digest(json.dumps(cases,ensure_ascii=False,sort_keys=True)),
        source_sha256={c['sample_id']:digest(c['code']) for c in cases},
        target_sha256={c['sample_id']:digest(json.dumps(c['targets'],ensure_ascii=False,sort_keys=True)) for c in cases},
        author_script_sha256=digest(Path(__file__).read_bytes())))


def verify_cases(cases, output, template=TEMPLATE):
    sys.path.insert(0,str(ROOT))
    from src.task3.cpp_sandbox import CppSandbox
    sandbox=CppSandbox(template);start=time.monotonic();evidence={};scratch=output/'jails'
    scratch.mkdir(parents=True,exist_ok=True)
    for n,c in enumerate(cases,1):
        jail,comp=sandbox.compile(c['code']+c['harness'],scratch)
        syntax=sandbox._call(jail,['/usr/bin/g++','-std=c++11','-fsyntax-only','-fmax-errors=3',
                                    '/work/source.cpp'],'',compile_phase=True)
        runs=[];witness=None;kinds=set()
        if comp['status']=='pass':
            for index,test in enumerate(c['tests']):
                result=sandbox.run(jail,test['input'])
                matches=result['stdout']==test['expected'] if c['checker']=='exact_bytes' else result['stdout'].split()==test['expected'].split()
                kind='timeout' if result['timeout'] else 'runtime_error' if result['returncode']!=0 else 'none' if matches else 'wrong_answer'
                record=dict(test_index=index,**test,**result,passed=kind=='none',failure_kind=kind)
                runs.append(record)
                if kind!='none':
                    kinds.add(kind)
                    if witness is None:witness=record
        else:
            kinds.add('compile_error');witness=dict(kind='compile_error',diagnostic=comp)
        evidence[c['sample_id']]=dict(source_sha256=digest(c['code']),syntax_only=syntax,
            compile_link=comp,tests=runs,witness=witness,observed_failure_kinds=sorted(kinds),
            all_tests_passed=comp['status']=='pass' and not kinds,
            solution_source_id=c['solution_source_id'],l4_source_sha256=digest(extract_l4(c)))
        dump(output/'cases'/f"{c['sample_id']}.private.json",evidence[c['sample_id']])
        shutil.rmtree(jail)
        print(f'Verified {n}/{len(cases)} {c["sample_id"]}',flush=True)
    failures=[]
    for c in cases:
        ev=evidence[c['sample_id']];repair=evidence[c['solution_source_id']]
        okay=(c['expected_failure_kind'] in ev['observed_failure_kinds']) if c['intended_defective'] else ev['all_tests_passed']
        if not okay or not repair['all_tests_passed']:failures.append(c['sample_id'])
        ev['repair_all_tests_passed']=repair['all_tests_passed']
        ev['repair_test_count']=len(repair['tests'])
        ev['l4_verified_by_clean_partner']=ev['l4_source_sha256']==repair['source_sha256'] and repair['all_tests_passed']
        dump(output/'cases'/f"{c['sample_id']}.private.json",ev)
    dump(output/'execution.private.json',evidence)
    author_review(cases,evidence,output)
    report=dict(passed=not failures,sources=len(cases),targets=sum(len(c['targets']) for c in cases),
        clean_sources=20,defective_sources=20,
        clean_all_tests_passed=sum(evidence[c['sample_id']]['all_tests_passed'] for c in cases if not c['intended_defective']),
        faults_witnessed=sum('wrong_answer' in evidence[c['sample_id']]['observed_failure_kinds'] for c in cases if c['intended_defective']),
        l4_verified=sum(v['l4_verified_by_clean_partner'] for v in evidence.values()),
        repair_all_tests_passed=sum(v['repair_all_tests_passed'] for v in evidence.values()),
        syntax_only_compile_calls=len(cases),compile_link_calls=len(cases),
        runtime_calls=sum(len(v['tests']) for v in evidence.values()),elapsed_seconds=time.monotonic()-start,
        failures=failures,model_calls=0,independent_human_review=False,
        runner='src.task3.cpp_sandbox.CppSandbox',template=str(template),
        template_ready_sha256=digest((template/'READY.json').read_bytes()),
        confinement='chroot + uid/gid/groups/capability drop + no_new_privs + seccomp allowlist + rlimits',
        runtime_limits=dict(wall_seconds=2,cpu_soft_seconds=1,cpu_hard_seconds=2,address_space_mib=512,
                            processes=1,open_fds=64,output_file_bytes=65536),
        compiler_limits=dict(wall_seconds=10,cpu_soft_seconds=4,cpu_hard_seconds=5,address_space_mib=512,
                             processes=4,open_fds=64,output_file_bytes=8388608),
        evidence_separation='Runtime witnesses, oracles, repairs, and author verdicts private; only syntax_only may be rendered as compiler input.',
        limitation='Finite bounded checks do not prove all-input correctness; synthetic agent-reviewed annotations, not independent gold.')
    dump(output/'summary.json',report)
    if failures:raise AssertionError(f'Verification failed: {failures}')
    return report


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--verify',action='store_true');ap.add_argument('--check',action='store_true')
    ap.add_argument('--verify-existing',action='store_true');ap.add_argument('--verification-dir',type=Path)
    args=ap.parse_args();cases=build_cases();validate_cases(cases)
    target=DEST/'final-new.private.json'
    if args.check:
        if target.exists():assert json.loads(target.read_text())==cases,'On-disk final differs from authored specification'
        print(json.dumps(dict(sources=len(cases),targets=160,families=10,clean=20,faulty=20)));return
    if args.verify_existing:
        assert json.loads(target.read_text())==cases,'Existing final differs from authoring code'
        if args.verification_dir is None or args.verification_dir.exists():
            raise ValueError('--verify-existing requires a fresh --verification-dir')
        print(json.dumps(verify_cases(cases,args.verification_dir),ensure_ascii=False,indent=2));return
    if target.exists():raise FileExistsError('Refusing to overwrite authored final; compare offline or use --check')
    dump(target,cases)
    catalog=json.loads((ROOT/'data/raw/task3-sft-v1/families.json').read_text())
    dump(VERIFY/'family-catalog-screen.json',dict(existing_families_read=len(catalog),
        existing_catalog_sha256=digest((ROOT/'data/raw/task3-sft-v1/families.json').read_bytes()),
        existing_catalog=[{k:c.get(k) for k in ('family_id','split','title','statement','invariant','cluster')} for c in catalog],
        new_families=[dict(family_id=f'V2E{i:02}',title=f['title'],structural_distinction=f['distinction']) for i,f in enumerate(FAMILIES,1)],
        review='Author examined all fifty existing specifications and invariants before choosing families.',
        public_screen_status='Root experiment runner performs complete public-source and cross-dataset screening before freeze.',
        limitations='Conceptual review cannot prove semantic independence; common C++ IO and container idioms remain shared.'))
    if args.verify:print(json.dumps(verify_cases(cases,VERIFY),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
