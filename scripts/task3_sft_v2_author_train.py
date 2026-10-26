#!/usr/bin/env python3
"""Private synthetic v2 train pairs; independent specification oracles and confined evidence.

No model API, GPU, evaluation-family source, or inference renderer is used here.
Only the 40 original train family statements/bindings are reused. The programs are
new implementations; structural overlap within the same problem remains expected.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import itertools
import json
import math
from pathlib import Path
import random
import re
import shutil
import sys

MOD=1000000007
FAMILIES=[*range(1,23),24,25,26,27,28,30,31,33,34,37,38,39,40,42,47,48,49,50]

def normalized_source(source):
    source=re.sub(r'//[^\n]*|/\*.*?\*/','',source,flags=re.S)
    tokens=re.findall(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[A-Za-z_]\w*|\d+|[^\s]',source)
    keywords=set('include int long short unsigned signed char bool void float double return if else for while do break continue switch case default const static struct class public private protected new delete nullptr true false auto using namespace template typename sizeof main first second lower_bound upper_bound reverse sort'.split())
    return ' '.join('ID' if re.fullmatch(r'[A-Za-z_]\w*',t) and t not in keywords else t for t in tokens)

def oracle(family_id, stdin):
    """Specification interpretation in Python, never derived from the C++ repair."""
    f=int(family_id[1:]); v=list(map(int,stdin.split())) if f not in (8,13,24,25,50,11) else []
    line=stdin.removesuffix('\n')
    def out(values):return ' '.join(map(str,values))+'\n'
    if f==1:return out([sum(v[1:])])
    if f==2:return out([sum(x%v[1]==0 for x in v[2:])])
    if f==3:
        # Number of independently necessary unit changes, enumerated per axis.
        return out([len(range(min(v[0],v[2]),max(v[0],v[2])))+len(range(min(v[1],v[3]),max(v[1],v[3])))])
    if f==4:
        a=v[1:];return out([max(j-i for i in range(len(a)) for j in range(i+1,len(a)+1) if len(set(a[i:j]))==1)])
    if f==5:return out(dict.fromkeys(v[1:]))
    if f==6:return out([sum(int(ch)**len(str(v[0])) for ch in str(v[0]))])
    if f==7:return out([len(set(range(v[0],v[1]+1))&set(range(v[2],v[3]+1)))])
    if f==8:return out([len(re.findall(r'[^ \t]+',line))])
    if f==9:return out([next((i for i,x in enumerate(v[2:]) if x==v[1]),-1)])
    if f==10:
        n,key=v[:2];a=v[2:];assert n==len(a)
        return out(a)+out([a.count(key)])+out([max(a) if a else 0])+out(x for x in a if x!=key)
    if f==11:
        t=stdin.split();n,threshold=map(int,t[:2]);records=[(t[2+2*i],int(t[3+2*i])) for i in range(n)]
        return out(z for row in records for z in row)+out([sum(s for _,s in records)])+out([sum(s>=threshold for _,s in records)])*2
    if f==12:return f'{v[0]+v[1]} {v[0]*v[1]}\n'
    if f==13:
        # Repeatedly remove an innermost pair, an independent stack-free oracle.
        s=line
        while '()' in s:s=s.replace('()','')
        return 'YES\n' if not s else 'NO\n'
    if f==14:
        n=v[0];a=v[1:];return out([sum(x for k,x in enumerate(a) if k//n==k%n)])
    if f==15:return out([v[0]**2+1])
    if f==16:return out([math.gcd(*v)])
    if f==17:return out([math.lcm(*v)])
    if f==18:
        n=v[0];return ('YES' if n>=2 and sum(n%d==0 for d in range(1,n+1))==2 else 'NO')+'\n'
    if f==19:return out([math.factorial(v[0])%MOD])
    if f==20:
        # Exact integer recurrence; modulo only at the oracle boundary.
        a,b=0,1
        for _ in range(v[0]):a,b=b,a+b
        return out([a%MOD])
    if f==21:return out([str(v[0]).count('0')])
    if f==22:return out([int(str(v[0])[::-1])])
    if f==24:
        kept=[]
        for ch in line:
            if kept and kept[-1]==ch:kept.pop()
            else:kept.append(ch)
        return ''.join(kept)+'\n'
    if f==25:return out(z for ch,g in itertools.groupby(line) for z in (ch,len(list(g))))
    if f==26:
        r,c=v[:2];return out(sum(v[2+i*c:2+(i+1)*c]) for i in range(r))
    if f==27:
        r,c=v[:2];a=v[2:];return ''.join(out(a[i*c+j] for i in range(r)) for j in range(c))
    if f==28:
        n=v[0];a=[v[1+i*n:1+(i+1)*n] for i in range(n)];return ''.join(out(row) for row in zip(*a[::-1]))
    if f==30:
        a=sorted(set(v[1:]),reverse=True);return out([a[1]]) if len(a)>1 else 'NONE\n'
    if f==31:return out(sorted(set(v[1:])))
    if f==33:return out(sorted(v[2:]))
    if f==34:
        n,q=v[:2];a=v[2:2+n];queries=v[2+n:];return ''.join(out([sum(a[l-1:r])]) for l,r in zip(queries[::2],queries[1::2]))
    if f==37:return out([next((i for i,a in enumerate(v[2:]) if a>=v[1]),v[0])])
    if f==38:return out([sum(a+b==v[1] for a,b in itertools.combinations(v[2:],2))])
    if f==39:
        product=math.prod(v[1:]);return out([(product>0)-(product<0)])
    if f==40:
        from fractions import Fraction
        q=Fraction(*v);return out([q.numerator,q.denominator])
    if f==42:
        import calendar
        return ('YES' if calendar.isleap(v[0]) else 'NO')+'\n'
    if f==47:
        n,W=v[:2];items=list(zip(v[2::2],v[3::2]));return out([max((sum(items[i][1] for i in range(n) if mask>>i&1) for mask in range(1<<n) if sum(items[i][0] for i in range(n) if mask>>i&1)<=W),default=0)])
    if f==48:
        n,S=v[:2];coins=v[2:]
        return out([sum(sum(q*c for q,c in zip(qs,coins))==S for qs in itertools.product(*(range(S//c+1) for c in coins)))])
    if f==49:
        # Component closure on original interval identities, independent of sweep C++.
        spans=list(zip(v[1::2],v[2::2]));remaining=set(range(len(spans)));groups=[]
        while remaining:
            component={remaining.pop()};changed=True
            while changed:
                take={j for j in remaining if any(max(spans[i][0],spans[j][0])<=min(spans[i][1],spans[j][1]) for i in component)}
                changed=bool(take);component|=take;remaining-=take
            groups.append((min(spans[i][0] for i in component),max(spans[i][1] for i in component)))
        return out(z for span in sorted(groups) for z in span)
    if f==50:
        return out([max((j-i for i in range(len(line)+1) for j in range(i,len(line)+1) if len(set(line[i:j]))==j-i),default=0)])
    raise ValueError(family_id)

def input_cases(f):
    rng=random.Random(4260+f)
    def seq(a,head=None):return (' '.join(map(str,[len(a)] if head is None else head))+'\n'+' '.join(map(str,a))+'\n')
    if f in (1,4,5,30,31,39):
        arrays=[[],[0],[-7],[5,5,5],[-4,2,-4,0,2],[100,-100,100],list(range(20)),[-9]*20]
        if f in (4,30,39):arrays=[a for a in arrays if a]+[[2,2,1,1,1],[-3,-2,-1]]
        if f in (30,31,39):arrays+=[[100]*100]
        return [seq(a) for a in arrays]+[seq([rng.randint(-5,5) for _ in range(rng.randint(1 if f in (4,30,39) else 0,20))]) for _ in range(5)]
    if f==2:return [seq(a,[len(a),k]) for k,a in [(1,[]),(2,[0]),(2,[-4,3,0]),(5,[-5,10,-2]),(1,[7,-9]),(3,[3,3,3]),(4,[1,2,3,4]),(5,[100,-100,0])]]+[seq([rng.randint(-100,100) for _ in range(20)],[20,k]) for k in range(1,6)]
    if f==3:return [' '.join(map(str,x))+'\n' for x in [(0,0,0,0),(0,0,0,2),(1,-2,-3,4),(-100,100,100,-100),(7,3,1,3),(2,-8,2,-9),(9,9,-9,-9),(4,-3,-2,-1)]]
    if f in (6,15,18,19,20,21,22,42):
        nums={6:[1,9,10,153,999999999,1000000000,987654321,10001],15:[-100,-9,-1,0,1,2,11,100],18:[0,1,2,3,4,9,25,49,97,9991,10000],19:[0,1,2,3,4,7,20,100,1000],20:[0,1,2,3,4,7,20,100,10000],21:[0,1,10,100,1001,1000000000,99009,777],22:[0,1,10,120,321,1000000000,90909,908172635],42:[1,4,100,400,1600,1900,2000,2024,2100,9999]}[f]
        return [str(n)+'\n' for n in nums]
    if f==7:return [f'{a} {b} {c} {d}\n' for a,b,c,d in [(-1,1,1,4),(0,0,0,0),(-20,20,-20,20),(-5,-2,1,3),(0,2,-5,-1),(1,4,2,3),(-4,5,-2,8),(7,7,6,8)]]
    if f==8:return [s+'\n' for s in ['', ' ', '\t','a','a b','ab\tcd','  a \tb  c\t','abcdefgh','one  two three','\talpha\tbeta\t']]
    if f in (9,37):return [seq(a,[len(a),x]) for a,x in [([],0),([1],1),([1],0),([1],2),([-4,-4,-4],-4),([-5,-2,0,0,9],0),([-5,-2,0,9],-3),([0]*20,0),([-100,100],100),([-100,100],99)]]
    if f==10:return [seq(a,[len(a),key]) for a,key in [([],0),([-2,-5,-2],-2),([0],0),([3,3,3],3),([-9,-2,-8],7),([5,1,5,2,5],5),([1,2,3],2),(list(range(20)),19),([-100,100],-100)]]
    if f==11:return [f'{len(a)} {threshold}\n'+''.join(f'name{i} {s}\n' for i,s in enumerate(a)) for a,threshold in [([],0),([0],0),([50,49,51],50),([100]*20,100),([1,2,3],4),([20,0,80],1),([7,7],7),([100,0],100),([3,9,2,7],5)]]
    if f in (12,16,17,40):
        pairs={12:[(0,0),(-3,2),(-100,100),(4,7),(1,1),(-2,-3),(99,-1),(100,100)],16:[(0,7),(7,0),(-18,12),(18,-12),(-18,-12),(1,999983),(1000000,500000),(17,19),(0,-1000000)],17:[(0,0),(0,7),(7,0),(6,8),(1,1),(17,19),(999983,1000000),(12,18)],40:[(0,-7),(0,4),(18,-12),(-18,12),(-18,-12),(1,999983),(1000000,500000),(17,19),(1000000,-1000000)]}[f]
        return [f'{a} {b}\n' for a,b in pairs]
    if f==13:return [s+'\n' for s in ['', '(',')','()','()()','(())','())(',')(','(()','('*20+')'*20]]
    if f in (14,26,27,28):
        dims=[(1,1),(2,2),(3,3),(4,4),(5,5),(2,3),(3,2),(1,5),(5,1)] if f in (26,27) else [(n,n) for n in [1,2,3,4,5,2,3,5]]
        if f in (26,27,28):dims+=[(10,10)]
        return [(' '.join(map(str,[r,c] if f in (26,27) else [r]))+'\n'+'\n'.join(' '.join(str((i*c+j)*3-17) for j in range(c)) for i in range(r))+'\n') for r,c in dims]
    if f==24:return [s+'\n' for s in ['', 'a','aa','abb','abba','abccba','aaabbb','abab','abbaaac','a'*100]]
    if f==25:return [s+'\n' for s in ['', 'a','aa','ab','abbccc','aaabbaa','abab','z'*100,'xxyzzzz']]
    if f==33:return [f'{len(a)} {len(b)}\n'+' '.join(map(str,a))+'\n'+' '.join(map(str,b))+'\n' for a,b in [([],[]),([1],[]),([],[2]),([1],[1]),([-5,0,0],[0,2,9]),([1,3,5],[2,4,6]),([-100]*20,[100]*20),([2,2,2],[2,2]),([-4,-1],[3])]]
    if f==34:
        arrays=[[1],[-5],[-2,0,7],[1,2,3,4],[-9]*20,[100,-100],[0]*10,list(range(20))]
        return [seq(a,[len(a),len(a)*(len(a)+1)//2 if len(a)<=10 else 3])+''.join(f'{l} {r}\n' for l,r in ([(l,r) for l in range(1,len(a)+1) for r in range(l,len(a)+1)] if len(a)<=10 else [(1,len(a)),(len(a),len(a)),(2,4)])) for a in arrays]
    if f==38:return [seq(a,[len(a),s]) for a,s in [([0],0),([1],2),([1,1],2),([-1,0,1],0),([2,2,2,2],4),([-100,100,0,0],0),(list(range(20)),11),([5,-3,5,-3],2),([1,2,3],9)]]
    if f==47:
        values=[([],0),([],30),([(2,3)],4),([(2,3)],1),([(2,3),(3,5)],5),([(1,2),(1,2),(2,3)],2),([(30,100)]*12,30),([(3,4),(4,8),(5,9)],8),([(1,1)],0)]
        return [f'{len(a)} {W}\n'+''.join(f'{w} {v}\n' for w,v in a) for a,W in values]
    if f==48:return [seq(a,[len(a),S]) for a,S in [([1],0),([1],4),([2],3),([1,2],4),([2,3],12),([2,5,7],20),([10],30),([1,3,5],10),([2,4,6,8,10],8)]]
    if f==49:return [f'{len(a)}\n'+''.join(f'{l} {r}\n' for l,r in a) for a in [[],[(1,1)],[(1,3),(3,7),(2,2)],[(-5,-1),(1,4)],[(1,10),(2,3),(4,6)],[(5,7),(1,6)],[(0,0),(0,1),(1,1)],[(-100,100),(-20,-10),(0,1)],[(7,9),(1,2),(2,5),(4,8)]]]
    if f==50:return [s+'\n' for s in ['', 'a','aaaa','abba','abcabcbb','pwwkew','abcdefghijklmnopqrst','abacdefg','a'*100]]
    raise ValueError(f)


def author_specs():
    specs=[]
    def add(f,code,before,after,labels,mechanism,diagnosis,repair,clean2,clean3,failure='wrong_answer'):
        code=code.strip()+'\n'
        if code.count(before)!=1:raise ValueError((f,before,code.count(before)))
        specs.append(dict(f=f,code=code,before=before,after=after,labels=labels,mechanism=mechanism,diagnosis=diagnosis,repair=repair,clean2=clean2,clean3=clean3,failure=failure))
    add(1,r'''
#include <iostream>
#include <vector>
int main() {
    int n; std::cin >> n;
    std::vector<int> slot(n+1, 0);
    for (int pos=1; pos<=n; ++pos) std::cin >> slot.at(pos);
    long long answer = 0;
    int remaining=n;
    while (remaining>0) answer += slot.at(remaining--);
    std::cout << answer << '\n';
}
''','long long answer = 0;','long long answer;', ['Lỗi logic'],
    'actual_use_before_initialization',
    'Biến answer trong main được đọc khi chưa khởi tạo, nên phép cộng dồn không có giá trị ban đầu xác định.',
    'Khởi tạo answer bằng không trước khi cộng các phần tử.',
    'Biến answer đã được khởi tạo và các chỉ số từ một đến n đều nằm trong slot.',
    'slot có thêm một ô cho cách đánh chỉ số từ một; vòng while đi từ cuối dãy về đầu và cộng mỗi phần tử đúng một lần. answer bắt đầu bằng không nên cả dãy rỗng cũng có tổng đúng.',failure='uninitialized_use_diagnostic')
    add(2,r'''
#include <algorithm>
#include <iostream>
#include <vector>
void add_match(int value, int divisor, int* hits) {
    if (value % divisor == 0) *hits += 1;
}
int main() {
    int n,k; std::cin >> n >> k;
    std::vector<int> values(n);
    for (auto& value : values) std::cin >> value;
    int hits=0;
    std::for_each(values.begin(), values.end(), [&](int value){ add_match(value,k,&hits); });
    std::cout << hits << '\n';
}
''','value % divisor == 0','value % divisor != 0',['Lỗi logic'],
    'helper_predicate_inversion',
    'Hàm add_match đếm phần tử không chia hết, trái yêu cầu đề.',
    'Đổi điều kiện trong add_match thành phần dư bằng không để chỉ tăng hits cho phần tử chia hết.',
    'Hàm add_match tăng đúng bộ đếm tại nơi gọi cho phần tử chia hết.',
    'Con trỏ hits trỏ tới bộ đếm trong main nên cập nhật của hàm phụ được giữ lại. Điều kiện phần dư bằng không áp dụng được cho số âm và số không; dãy rỗng không làm tăng bộ đếm.')
    add(3,r'''
#include <iostream>
int main() {
    int x,y,goal_x,goal_y; std::cin >> x >> y >> goal_x >> goal_y;
    int steps=0;
    while (x!=goal_x) { x += x<goal_x ? 1 : -1; ++steps; }
    while (y!=goal_y) { y += y<goal_y ? 1 : -1; steps += 1; }
    std::cout << steps << '\n';
}
''','steps += 1;','steps += 2;',['Lỗi logic'],
    'unit_step_cost_invariant',
    'Vòng dịch chuyển theo trục y tăng steps hai lần cho mỗi bước đơn vị, nên đếm thừa bước dọc.',
    'Chỉ tăng steps một đơn vị cho mỗi lần y tiến về goal_y.',
    'Hai vòng lặp đều tiến về tọa độ đích và đếm đúng từng bước đơn vị.',
    'Mỗi vòng chỉ thay đổi một tọa độ về phía đích, nên khoảng cách trên trục đó giảm sau mỗi lượt. Đếm một đơn vị cho mỗi lượt trên cả hai trục cho số bước ít nhất và không làm hai độ lệch triệt tiêu nhau.')
    add(4,r'''
#include <algorithm>
#include <iostream>
#include <vector>
int main() {
    int n; std::cin >> n;
    std::vector<int> values(n);
    for (int& x : values) std::cin >> x;
    int longest=0;
    for (int begin=0; begin<n; ++begin) {
        int end=begin;
        while (end<n && values[end]==values[begin]) ++end;
        longest=std::max(longest,end-begin);
    }
    std::cout << longest << '\n';
}
''','end-begin);','end-begin-1);',['Lỗi logic'],
    'half_open_run_length',
    'Biểu thức cập nhật longest trừ thừa một đơn vị khỏi độ dài đoạn nửa mở từ begin đến end.',
    'Dùng end-begin làm độ dài vì end đã đứng ngay sau phần tử cuối của đoạn.',
    'Phép tính end-begin đúng với đoạn nửa mở đã được vòng while tìm thấy.',
    'Với mỗi vị trí đầu, end dừng tại vị trí đầu tiên khác giá trị hoặc cuối dãy. Vì end không thuộc đoạn, end-begin chính là số phần tử; lấy lớn nhất trên mọi vị trí đầu bao gồm cả đoạn kết thúc ở cuối dãy.')
    add(5,r'''
#include <array>
#include <iostream>
int main() {
    int n; std::cin >> n;
    std::array<bool,201> seen{};
    while (n--) {
        int value; std::cin >> value;
        int bucket=value+100;
        if (!seen.at(bucket)) {
            std::cout << value << ' ';
            seen.at(bucket) = true;
        }
    }
    std::cout << '\n';
}
''','seen.at(bucket) = true;','seen.at(bucket) = false;',['Lỗi logic'],
    'seen_state_persistence',
    'Nhánh xuất trong main để seen của giá trị vừa in bằng false, nên lần xuất hiện sau vẫn bị coi là mới.',
    'Đánh dấu seen tại bucket thành true ngay sau lần xuất đầu tiên.',
    'Mảng seen được khởi tạo rỗng và lưu bền trạng thái của các giá trị đã xuất.',
    'Độ lệch chỉ số đưa toàn bộ miền giá trị vào các ô hợp lệ của seen. Xuất ngay lần đầu gặp giữ thứ tự đầu vào, còn trạng thái đã đánh dấu ngăn mọi lần lặp về sau; dãy rỗng chỉ tạo xuống dòng.')
    add(6,r'''
#include <iostream>
#include <string>
long long integer_power(long long base, unsigned exponent) {
    long long result=1;
    while (exponent) {
        if (exponent&1u) result*=base;
        exponent >>= 1u;
        if (exponent) base*=base;
    }
    return result;
}
int main() {
    std::string digits; std::cin >> digits;
    unsigned degree=digits.size();
    long long answer=0;
    for (char ch : digits) answer+=integer_power(ch-'0', degree);
    std::cout << answer << '\n';
}
''','unsigned degree=digits.size();','unsigned degree=digits.size()-1;',['Lỗi logic'],
    'digit_exponent_off_by_one',
    'Biến degree trong main nhỏ hơn số chữ số một đơn vị nên các lũy thừa dùng sai số mũ.',
    'Gán degree đúng bằng digits.size() trước khi tính lũy thừa nguyên.',
    'degree bằng số chữ số và integer_power chỉ dùng phép nhân nguyên.',
    'Đầu vào được đọc dưới dạng chuỗi để giữ số lượng chữ số. Hàm bình phương và nhân tính đúng lũy thừa nguyên; kiểu long long chứa được từng lũy thừa và tổng trong miền đề cho, kể cả khi tổng vượt int có dấu.')
    add(7,r'''
#include <iostream>
int main() {
    int l1,r1,l2,r2; std::cin >> l1 >> r1 >> l2 >> r2;
    int count=0;
    for (int value=-20; value<=20; ++value)
        if (l1<=value && value<=r1 && l2<=value && value<=r2) ++count;
    std::cout << count << '\n';
}
''','value<=r2','value<r2',['Lỗi edge case'],
    'closed_endpoint_membership',
    'Điều kiện trong vòng đếm loại đầu phải r2 của đoạn đóng thứ hai khi đầu mút đó thuộc giao.',
    'Cho phép value bằng r2 trong phép kiểm tra thuộc đoạn thứ hai.',
    'Phép kiểm tra thuộc cả hai đoạn tính đủ các đầu mút đóng.',
    'Vòng duyệt bao phủ toàn bộ miền tọa độ được phép. Mỗi số nguyên chỉ tăng bộ đếm nếu thuộc đồng thời hai đoạn, nên giao rỗng không được đếm và đầu mút chung vẫn được tính.')
    add(8,r'''
#include <iostream>
#include <string>
int main() {
    std::string line; std::getline(std::cin,line);
    bool previous_gap=true;
    int words=0;
    for (char ch : line) {
        bool gap=(ch==' ' || ch=='\t');
        if (!gap && previous_gap) ++words;
        previous_gap=gap;
    }
    std::cout << words << '\n';
}
''','if (!gap && previous_gap)','if (!gap)',['Lỗi mảng/chuỗi'],
    'word_transition_invariant',
    'Điều kiện tăng words trong main đếm từng ký tự không phân tách thay vì chỉ đếm lúc bắt đầu từ.',
    'Chỉ tăng words khi ký tự hiện tại không phân tách và previous_gap đang đúng.',
    'words chỉ tăng tại chuyển tiếp từ dấu phân tách sang ký tự của từ.',
    'getline giữ toàn bộ dòng, kể cả tab và dấu cách. previous_gap bắt đầu ở trạng thái ngoài từ và cập nhật theo mỗi ký tự, nên từ đầu dòng được tính và các ký tự còn lại trong cùng từ không làm tăng kết quả.')
    add(9,r'''
#include <algorithm>
#include <iostream>
#include <vector>
int main() {
    int n,needle; std::cin >> n >> needle;
    std::vector<int> a(n);
    for (int& x : a) std::cin >> x;
    auto equal=std::equal_range(a.begin(),a.end(),needle);
    if (equal.first==equal.second) std::cout << -1 << '\n';
    else std::cout << std::distance(a.begin(),equal.first) << '\n';
}
''','std::distance(a.begin(),equal.first)','std::distance(a.begin(),equal.second)',['Lỗi thuật toán'],
    'equal_range_endpoint_identity',
    'Lệnh xuất trong main dùng equal.second là vị trí sau nhóm bằng needle, nên không trả lần xuất hiện đầu.',
    'Lấy khoảng cách từ a.begin() đến equal.first ở nhánh đã tìm thấy.',
    'Nhánh tìm thấy dùng đầu trái của equal_range làm vị trí xuất hiện đầu.',
    'Trên dãy không giảm, equal_range bao quanh toàn bộ nhóm bằng needle. Hai đầu bằng nhau biểu thị không có phần tử phù hợp, kể cả dãy rỗng; đầu trái của nhóm là chỉ số cần trả khi tìm thấy.')
    add(10,r'''
#include <algorithm>
#include <vector>
struct Node { int value; Node* next; };
Node* build(const std::vector<int>& a) {
    Node* head=nullptr;
    for (auto it=a.rbegin(); it!=a.rend(); ++it) head=new Node{*it,head};
    return head;
}
int count_value(Node* head,int key) {
    return head ? (head->value==key)+count_value(head->next,key) : 0;
}
int maximum(Node* head) {
    if (!head) return 0;
    return head->next ? std::max(head->value,maximum(head->next)) : head->value;
}
void erase_value(Node*& head,int key) {
    while (head && head->value==key) { Node* gone=head; head=head->next; delete gone; }
    if (head) erase_value(head->next,key);
}
''',r'''    while (head && head->value==key) { Node* gone=head; head=head->next; delete gone; }
    if (head) erase_value(head->next,key);''',r'''    (void)head;
    (void)key;''',['Lỗi hàm'],
    'multi_function_erase_omission',
    'Hàm erase_value không thực hiện thao tác xóa nào nên giữ lại các node bằng key.',
    'Trong erase_value, tháo và xóa mọi node khớp ở đầu rồi tiếp tục xử lý phần đuôi qua tham chiếu.',
    'Các hàm thực hiện đủ việc tạo, đếm, lấy lớn nhất và xóa node theo yêu cầu riêng.',
    'build thêm đầu từ cuối vector nên giữ thứ tự gốc. Hai hàm truy vấn dừng ở danh sách rỗng và maximum không lấy số không làm mốc cho danh sách âm. erase_value cập nhật liên kết qua tham chiếu nên xóa được cả đầu danh sách và các node khớp liên tiếp.')
    add(11,r'''
#include <iostream>
#include <numeric>
#include <string>
#include <vector>
struct Record { std::string name; int score; };
std::vector<Record> prob1(std::istream& in,int n) {
    std::vector<Record> result;
    while (n--) { Record item; in>>item.name>>item.score; result.push_back(item); }
    return result;
}
int prob2(const std::vector<Record>& a) {
    return std::accumulate(a.begin(),a.end(),0,[](int sum,const Record& item){return sum+item.score;});
}
int prob3(const std::vector<Record>& a,int threshold) {
    int answer=0;
    for (auto it=a.rbegin(); it!=a.rend(); ++it) answer+=(it->score>=threshold);
    return answer;
}
void prob4(const std::vector<Record>& a,int threshold) { std::cout<<prob3(a,threshold)<<'\n'; }
''',r'''int prob2(const std::vector<Record>& a) {
    return std::accumulate(a.begin(),a.end(),0,[](int sum,const Record& item){return sum+item.score;});
}''',r'''int prob2(const std::vector<Record>& a);''',['Lỗi biên dịch','Lỗi hàm'],
    'multi_function_definition_omission',
    'Hàm prob2 chỉ có khai báo nên harness gọi hàm này bị lỗi liên kết do thiếu định nghĩa.',
    'Bổ sung thân prob2 cộng score của mọi bản ghi và trả tổng, bắt đầu bằng không.',
    'Bốn hàm có đầy đủ định nghĩa và prob2 cộng đúng điểm của các bản ghi.',
    'prob1 nối các bản ghi theo thứ tự đọc; prob2 cộng score với giá trị đầu bằng không. prob3 duyệt ngược vẫn đếm đủ các điểm đạt ngưỡng, kể cả bằng ngưỡng; prob4 xuất chính kết quả đó rồi xuống dòng.',failure='link_error')
    add(12,r'''
#include <iostream>
#include <sstream>
int main() {
    int left,right; std::cin >> left >> right;
    std::ostringstream line;
    line << left+right << ' ' << left*right;
    std::cout << line.str() << '\n';
}
''',"<< ' ' << left*right;","<< '\\t' << left*right;",['Lỗi nhập/xuất'],
    'exact_bytes_separator',
    'Dòng ghép kết quả trong main dùng tab giữa tổng và tích, trái yêu cầu một dấu cách ASCII.',
    'Thay ký tự tab phân tách bằng đúng một dấu cách ASCII.',
    'Dòng kết quả dùng đúng một dấu cách giữa tổng và tích và kết thúc bằng LF.',
    'ostringstream chỉ ghép hai số theo đúng thứ tự và một dấu cách ở giữa. Lệnh xuất bổ sung duy nhất ký tự xuống dòng, nên không có khoảng trắng đầu hoặc cuối dòng và không có lời nhắc.')
    add(13,r'''
#include <iostream>
#include <string>
#include <vector>
bool accepted(const std::string& line) {
    std::vector<char> opens;
    for (char ch : line) {
        if (ch=='(') opens.push_back(ch);
        else {
            if (opens.empty()) return false;
            opens.pop_back();
        }
    }
    return opens.empty();
}
int main() {
    std::string line; std::getline(std::cin,line);
    std::cout << (accepted(line)?"YES":"NO") << '\n';
}
''','return opens.empty();','return true;',['Lỗi thuật toán'],
    'unclosed_parenthesis_postcondition',
    'Lệnh return cuối accepted chấp nhận cả khi còn ngoặc mở trong opens, nên bỏ qua ngoặc chưa đóng.',
    'Chỉ trả true ở cuối khi opens rỗng sau khi đã ghép hết ngoặc đóng.',
    'accepted loại ngoặc đóng không có cặp và chỉ chấp nhận khi không còn ngoặc mở.',
    'Mỗi ngoặc mở thêm một phần tử vào opens, còn ngoặc đóng lấy ra một phần tử đã có. Kiểm tra rỗng trước khi lấy ngăn ghép sai thứ tự; điều kiện rỗng cuối cùng ngăn bỏ sót ngoặc mở và vẫn chấp nhận dòng rỗng.')
    add(14,r'''
#include <iostream>
#include <vector>
int main() {
    int n; std::cin >> n;
    std::vector<int> cells(n*n+1);
    for (int index=1; index<=n*n; ++index) std::cin >> cells.at(index);
    int diagonal=0;
    for (int row=1; row<=n; ++row) diagonal+=cells.at((row-1)*n+row);
    std::cout << diagonal << '\n';
}
''','std::vector<int> cells(n*n+1);','std::vector<int> cells(n*n);',['Lỗi mảng/chuỗi'],
    'checked_one_based_capacity',
    'cells chỉ có n*n ô nhưng vòng đọc dùng chỉ số đến n*n, nên cells.at ném ngoại lệ vượt phạm vi.',
    'Cấp phát thêm một ô cho cells để chỉ số từ một đến n*n đều hợp lệ.',
    'cells có đủ dung lượng cho cách lưu phẳng bắt đầu từ chỉ số một.',
    'Vòng đọc dùng toàn bộ các chỉ số từ một tới n*n, và ô bổ sung giữ chỉ số cuối hợp lệ. Công thức của vòng cộng chọn đúng cột trùng với hàng trong ma trận gốc nên chỉ lấy đường chéo chính.',failure='runtime_error')
    add(15,r'''
#include <iostream>
struct Polynomial {
    int operator()(int value) const { return value*value+1; }
};
int main() {
    int value; std::cin >> value;
    Polynomial evaluate;
    std::cout << evaluate(value) << '\n';
}
''','int main() {','int run() {',['Lỗi biên dịch'],
    'missing_program_entry_point',
    'Chương trình định nghĩa run thay vì main nên thiếu điểm vào khi liên kết chương trình đầy đủ.',
    'Đổi tên hàm run thành main để cung cấp điểm vào của chương trình.',
    'Chương trình có main và toán tử gọi của Polynomial được định nghĩa đầy đủ.',
    'main đọc giá trị rồi gọi đối tượng Polynomial để tính bình phương cộng một. Mọi định nghĩa được dùng đều nằm trong tệp và phép tính nằm trong giới hạn kiểu int của miền đầu vào.',failure='link_error')
    add(16,r'''
#include <cstdlib>
#include <iostream>
long long gcd_recursive(long long a,long long b) {
    if (b==0) return a;
    return gcd_recursive(b,a%b);
}
int main() {
    long long a,b; std::cin >> a >> b;
    std::cout << gcd_recursive(std::llabs(a),std::llabs(b)) << '\n';
}
''','if (b==0) return a;','if (b==0) return 1;',['Lỗi logic'],
    'gcd_recursive_base_value',
    'Nhánh dừng của gcd_recursive trả hằng một thay vì giá trị a đang chứa UCLN.',
    'Trả a khi b bằng không để giữ kết quả của các bước lấy dư.',
    'Nhánh dừng trả đúng UCLN và đầu vào đã được chuyển thành độ lớn.',
    'Hàm đệ quy thay cặp số bằng số thứ hai và phần dư nên giữ tập ước chung và tiến tới số dư không. Tại đó a là UCLN; lấy độ lớn trước khi gọi bảo đảm kết quả không âm, kể cả khi một đầu vào bằng không.')
    add(17,r'''
#include <algorithm>
#include <iostream>
long long gcd_positive(long long a,long long b) {
    return b ? gcd_positive(b,a%b) : a;
}
long long lcm_value(long long a,long long b) {
    if (!a || !b) return 0;
    return a*(b/gcd_positive(a,b));
}
int main() {
    long long a,b; std::cin>>a>>b;
    std::cout<<lcm_value(a,b)<<'\n';
}
''','if (!a || !b) return 0;','if (!a || !b) return std::max(a,b);',['Lỗi edge case'],
    'lcm_zero_identity',
    'Nhánh có số không trong lcm_value trả số lớn hơn nên sai khi chỉ một đầu vào bằng không.',
    'Cho nhánh có ít nhất một đầu vào bằng không trả về không.',
    'lcm_value trả không khi có số không và dùng UCLN cho các trường hợp còn lại.',
    'Nhánh riêng của số không tránh phép chia không hợp lệ khi cả hai đầu vào đều bằng không. Với hai số dương, chia một thừa số cho UCLN trước khi nhân cho BCNN, và long long chứa được kết quả trong miền đầu vào.')
    add(18,r'''
#include <iostream>
#include <vector>
int main() {
    int n; std::cin >> n;
    std::vector<bool> prime(n+1,true);
    prime[0]=false;
    if (n>=1) prime[1]=false;
    for (int p=2; p*p<=n; ++p)
        if (prime[p]) for (int multiple=p*p; multiple<=n; multiple+=p) prime[multiple]=false;
    std::cout << (prime[n]?"YES":"NO") << '\n';
}
''','prime[multiple]=false;','prime[multiple]=true;',['Lỗi thuật toán'],
    'sieve_composite_elimination',
    'Vòng sàng gán prime của các bội số thành true nên không loại được hợp số.',
    'Gán prime[multiple] thành false khi đánh dấu các bội từ p*p.',
    'Vòng sàng loại các bội hợp số và đánh dấu riêng các số nhỏ hơn hai.',
    'Mỗi hợp số có một ước nguyên tố không vượt căn bậc hai của nó và được đánh dấu ở vòng tương ứng. Chỉ số sàng nằm trong n+1 ô; việc loại riêng các số nhỏ hơn hai bảo đảm cả biên nhỏ đều được xử lý.')
    add(19,r'''
#include <iostream>
const long long modulus=1000000007;
long long product(int left,int right) {
    if (left>right) return 1;
    if (left==right) return left;
    int mid=(left+right)/2;
    return product(left,mid)*product(mid+1,right)%modulus;
}
int main() {
    int n; std::cin >> n;
    std::cout << product(1,n) << '\n';
}
''','product(left,mid)*product(mid+1,right)','product(left,mid-1)*product(mid+1,right)',['Lỗi thuật toán'],
    'product_partition_coverage',
    'Hai lời gọi trong product đều bỏ qua mid nên tích thiếu thừa số ở vị trí chia đoạn.',
    'Cho lời gọi bên trái bao gồm mid để hai đoạn con phủ hết đoạn ban đầu.',
    'Hai đoạn con trong product phủ đủ các thừa số và không chồng nhau.',
    'Hàm chia đoạn thành phần trái kết thúc ở mid và phần phải bắt đầu sau mid, rồi nhân các tích theo modulo. Đoạn rỗng trả tích đơn vị, nên quy ước giai thừa tại không được giữ; kiểu long long chứa được tích của hai phần dư.')
    add(20,r'''
#include <iostream>
#include <vector>
int main() {
    int n; std::cin >> n;
    std::vector<long long> fib(n+2,0);
    fib[1]=1;
    for (int i=2; i<=n; ++i) fib[i]=(fib[i-1]+fib[i-2])%1000000007;
    std::cout << fib[n] << '\n';
}
''','fib[i-1]+fib[i-2]','fib[i-1]+fib[i-1]',['Lỗi logic'],
    'fibonacci_two_predecessors',
    'Công thức cập nhật fib dùng hai lần phần tử ngay trước nên không theo tổng hai phần tử liền trước.',
    'Dùng fib[i-1]+fib[i-2] trước khi lấy modulo.',
    'Mỗi phần tử fib được tính từ hai phần tử liền trước đã có.',
    'Mảng có đủ chỗ để khởi tạo hai giá trị đầu ngay cả khi n bằng không. Vòng lặp đi theo chỉ số tăng dần, áp dụng đúng hệ thức và lấy modulo ở mỗi lượt; cuối cùng xuất đúng phần tử tại n.')
    add(21,r'''
#include <algorithm>
#include <iostream>
#include <string>
int main() {
    unsigned long long value; std::cin >> value;
    std::string decimal=std::to_string(value);
    std::cout << std::count(decimal.begin(),decimal.end(),'0') << '\n';
}
''',"decimal.end(),'0')","decimal.end(),'O')",['Lỗi logic'],
    'digit_character_identity',
    'Lệnh count trong main tìm chữ cái O thay vì chữ số 0 nên bỏ sót chữ số cần đếm.',
    'Dùng ký tự chữ số 0 làm giá trị tìm của std::count.',
    'std::count tìm đúng chữ số 0 trong biểu diễn thập phân của giá trị.',
    'Chuyển giá trị đã đọc sang chuỗi tạo đúng biểu diễn thập phân thông thường, gồm cả biểu diễn của số không. Đếm ký tự chữ số không trong toàn bộ chuỗi vì vậy bao gồm cả các chữ số ở giữa và cuối số.')
    add(22,r'''
#include <algorithm>
#include <iostream>
#include <string>
int main() {
    long long n; std::cin >> n;
    std::string decimal=std::to_string(n);
    std::reverse(decimal.begin(),decimal.end());
    std::cout << std::stoll(decimal) << '\n';
}
''','std::reverse(decimal.begin(),decimal.end());','std::sort(decimal.begin(),decimal.end());',['Lỗi thuật toán'],
    'reverse_vs_sort_order',
    'Lệnh sort trong main sắp chữ số tăng dần nên làm mất thứ tự đảo của biểu diễn ban đầu.',
    'Dùng std::reverse trên toàn bộ decimal thay cho std::sort.',
    'std::reverse đảo đúng thứ tự chữ số trước khi chuyển lại thành số nguyên.',
    'Chuỗi thập phân được đảo nguyên vẹn nên vị trí từng chữ số được đổi theo yêu cầu. stoll chuyển chuỗi đảo thành giá trị số nguyên và tự loại các số không ở đầu, đồng thời vẫn xử lý được đầu vào bằng không.')
    add(24,r'''
#include <iostream>
#include <string>
int main() {
    std::string reduced; std::getline(std::cin,reduced);
    bool erased=true;
    while (erased) {
        erased=false;
        for (std::size_t i=0; i+1<reduced.size();) {
            if (reduced[i]==reduced[i+1]) {
                reduced.erase(i,2); erased=true; break;
            }
            ++i;
        }
    }
    std::cout << reduced << '\n';
}
''','            ++i;','            i+=2;',['Lỗi vòng lặp'],
    'adjacent_pair_scan_progress',
    'Bước tăng i trong vòng tìm cặp nhảy qua một vị trí nên có thể bỏ sót cặp bằng nhau kề nhau.',
    'Tăng i từng đơn vị khi chưa xóa cặp để xét mọi cặp kề nhau.',
    'Vòng tìm cặp xét đủ mọi vị trí và bắt đầu lại sau mỗi lần xóa.',
    'Mỗi lần duyệt chọn cặp bằng nhau ngoài cùng bên trái rồi xóa và tìm lại từ đầu. Cách rút gọn này cho cùng chuỗi còn lại như xử lý trái sang phải, vì các ký tự đã giữ chỉ bị thay đổi bởi một cặp mới vừa trở thành kề nhau; mỗi lần xóa đều giảm độ dài nên vòng lặp kết thúc.')
    add(25,r'''
#include <iostream>
#include <string>
void emit(const std::string& text,std::size_t begin) {
    if (begin==text.size()) return;
    std::size_t end=text.find_first_not_of(text[begin],begin);
    if (end==std::string::npos) end=text.size();
    std::cout << text[begin] << ' ' << end-begin << ' ';
    emit(text,end);
}
int main() {
    std::string text; std::getline(std::cin,text);
    emit(text,0);
    std::cout << '\n';
}
''',"<< end-begin << ' ';","<< end-begin+1 << ' ';",['Lỗi logic'],
    'run_terminator_exclusion',
    'Biểu thức xuất độ dài trong emit cộng thừa một đơn vị dù end đã là vị trí ngoài đoạn.',
    'Xuất end-begin để đếm đúng các vị trí từ begin đến ngay trước end.',
    'emit lấy ký tự đầu và đúng độ dài của từng đoạn bằng nhau liên tiếp.',
    'find_first_not_of xác định ký tự đầu tiên khác ký tự đang xét; nếu không còn thì end là cuối chuỗi. Độ dài đoạn nửa mở là end-begin, và lời gọi tiếp theo bắt đầu đúng ở end nên không bỏ sót ký tự; dòng rỗng không phát sinh đoạn.')
    add(26,r'''
#include <iostream>
#include <vector>
int main() {
    int rows,cols; std::cin >> rows >> cols;
    std::vector<int> totals(rows,0);
    for (int index=0; index<rows*cols; ++index) {
        int value; std::cin >> value;
        totals.at(index/cols)+=value;
    }
    for (int total : totals) std::cout << total << ' ';
    std::cout << '\n';
}
''','totals.at(index/cols)','totals.at(index%rows)',['Lỗi logic'],
    'flat_input_row_mapping',
    'Phép lấy index%rows trong main phân phối dữ liệu theo vòng thay vì nhóm các phần tử của cùng hàng.',
    'Dùng index/cols làm chỉ số hàng khi cộng vào totals.',
    'Phép chia index/cols đưa mỗi phần tử đọc vào tổng của đúng hàng.',
    'Input đi theo thứ tự hàng, nên mỗi nhóm cols giá trị liên tiếp thuộc cùng một hàng. Các tổng được khởi tạo riêng bằng không và xuất theo thứ tự chỉ số hàng; xử lý theo dòng phẳng vẫn đúng với ma trận chữ nhật.')
    add(27,r'''
#include <iostream>
#include <vector>
int main() {
    int rows,cols; std::cin >> rows >> cols;
    std::vector<std::vector<int>> transpose(cols,std::vector<int>(rows));
    for (int row=0; row<rows; ++row)
        for (int col=0; col<cols; ++col) {
            int value; std::cin >> value;
            transpose.at(col).at(row)=value;
        }
    for (const auto& row : transpose) {
        for (int value : row) std::cout << value << ' ';
        std::cout << '\n';
    }
}
''','transpose.at(col).at(row)=value;','transpose.at(col).at(rows-1-row)=value;',['Lỗi logic'],
    'transpose_coordinate_mapping',
    'Lệnh gán vào transpose đảo chỉ số hàng gốc, nên mỗi hàng của kết quả chuyển vị bị ngược thứ tự.',
    'Lưu value vào transpose[col][row] để chỉ hoán đổi hai tọa độ.',
    'Lệnh gán hoán đổi đúng chỉ số hàng và cột của từng phần tử.',
    'Ma trận kết quả có cols hàng và rows cột, phù hợp cả khi ma trận gốc không vuông. Mỗi phần tử được đặt vào hàng bằng cột gốc và cột bằng hàng gốc, rồi các hàng kết quả được xuất theo thứ tự.')
    add(28,r'''
#include <iostream>
#include <vector>
int main() {
    int n; std::cin >> n;
    std::vector<std::vector<int>> rotated(n,std::vector<int>(n));
    for (int row=0; row<n; ++row)
        for (int col=0; col<n; ++col) {
            int value; std::cin >> value;
            rotated.at(col).at(n-1-row)=value;
        }
    for (const auto& row : rotated) {
        for (int value : row) std::cout << value << ' ';
        std::cout << '\n';
    }
}
''','rotated.at(col).at(n-1-row)=value;','rotated.at(n-1-col).at(row)=value;',['Lỗi logic'],
    'clockwise_coordinate_mapping',
    'Lệnh gán vào rotated ánh xạ theo chiều ngược kim đồng hồ, trái chiều xoay mà đề yêu cầu.',
    'Đưa phần tử gốc ở row,col tới rotated[col][n-1-row].',
    'Ánh xạ vào rotated đưa từng phần tử đúng vị trí sau khi xoay theo chiều kim đồng hồ.',
    'Cột gốc trở thành hàng mới, còn hàng gốc được đảo để thành cột mới. Ánh xạ này là một song ánh trong ma trận vuông, nên mọi ô được gán đúng một lần và các hàng được xuất đúng thứ tự.')
    add(30,r'''
#include <array>
#include <iostream>
int main() {
    int n; std::cin >> n;
    std::array<bool,201> present{};
    while (n--) { int value; std::cin >> value; present.at(value+100)=true; }
    int distinct=0;
    for (int value=100; value>=-100; --value) {
        if (present.at(value+100)) {
            ++distinct;
            if (distinct==2) { std::cout<<value<<'\n'; return 0; }
        }
    }
    std::cout << "NONE\n";
}
''','int distinct=0;','int distinct=1;',['Lỗi logic'],
    'distinct_rank_initialization',
    'Biến distinct bắt đầu từ một nên giá trị lớn nhất đã bị nhận thành giá trị lớn thứ hai.',
    'Khởi tạo distinct bằng không trước khi duyệt các giá trị hiện diện theo thứ tự giảm.',
    'distinct bắt đầu từ không và chỉ tăng một lần cho mỗi giá trị khác nhau.',
    'Bảng present gộp các bản sao của cùng một giá trị. Duyệt toàn bộ miền theo thứ tự giảm và trả khi số giá trị đã thấy đạt hai cho giá trị lớn thứ hai phân biệt; nếu chưa đạt thì xuất NONE.')
    add(31,r'''
#include <array>
#include <iostream>
int main() {
    int n; std::cin >> n;
    std::array<unsigned,201> frequency{};
    while (n--) { int value; std::cin >> value; ++frequency.at(value+100); }
    for (int value=-100; value<=100; ++value)
        if (frequency.at(value+100)) std::cout << value << ' ';
    std::cout << '\n';
}
''','value<=100;','value<100;',['Lỗi edge case'],
    'domain_upper_endpoint',
    'Vòng xuất trong main dừng trước giá trị 100 nên làm mất phần tử hợp lệ ở biên trên của miền.',
    'Cho vòng xuất xét cả value bằng 100.',
    'Vòng xuất xét toàn bộ miền và chỉ in một lần cho giá trị có tần suất dương.',
    'Mảng frequency đủ chỗ cho mọi giá trị đầu vào sau khi dịch chỉ số. Duyệt miền tăng dần tạo đúng thứ tự và chỉ kiểm tra tần suất dương nên các bản sao không làm tăng số lần xuất; dãy rỗng không xuất số nào.')
    add(33,r'''
#include <algorithm>
#include <iostream>
#include <vector>
int main() {
    int n,m; std::cin >> n >> m;
    std::vector<int> merged(n+m);
    for (int& value : merged) std::cin >> value;
    std::stable_sort(merged.begin(),merged.end());
    for (int value : merged) std::cout << value << ' ';
    std::cout << '\n';
}
''','    std::stable_sort(merged.begin(),merged.end());',r'''    std::stable_sort(merged.begin(),merged.end());
    merged.erase(std::unique(merged.begin(),merged.end()),merged.end());''',['Lỗi thuật toán'],
    'merge_multiplicity_preservation',
    'Lệnh unique rồi erase trong main xóa các bản sao bằng nhau dù đề yêu cầu giữ đủ mọi phần tử.',
    'Bỏ thao tác loại trùng và xuất toàn bộ merged sau khi sắp xếp.',
    'Sắp xếp dãy nối vẫn giữ đủ mọi bản sao và tạo thứ tự không giảm.',
    'Đọc liên tiếp hai dãy vào một vector giữ nguyên số lượng của tất cả giá trị. stable_sort sắp thứ tự mà không xóa phần tử, đáp ứng đầu ra dù không tận dụng tính đã sắp của hai dãy; kích thước đã cho cho phép cách làm này.')
    add(34,r'''
#include <iostream>
#include <numeric>
#include <vector>
int main() {
    int n,q; std::cin >> n >> q;
    std::vector<int> data(n+1,0);
    for (int pos=1; pos<=n; ++pos) std::cin >> data.at(pos);
    while (q--) {
        int left,right; std::cin >> left >> right;
        auto first=data.begin()+left;
        auto past=data.begin()+right+1;
        std::cout << std::accumulate(first,past,0LL) << '\n';
    }
}
''','auto first=data.begin()+left;','auto first=data.begin()+left+1;',['Lỗi logic'],
    'closed_query_iterator_range',
    'Iterator first trong main bắt đầu sau left nên tổng truy vấn bỏ sót phần tử đầu trái.',
    'Đặt first tại data.begin()+left và giữ past ngay sau right.',
    'Khoảng iterator của accumulate bao gồm đúng hai đầu của đoạn truy vấn đóng.',
    'Mảng thêm một ô để dùng chỉ số theo đề. accumulate xét khoảng nửa mở từ left tới right+1, tương đương đoạn đóng yêu cầu; kiểu khởi tạo long long giữ tổng trong kiểu đủ rộng và truy vấn một phần tử vẫn được cộng.')
    add(37,r'''
#include <algorithm>
#include <iostream>
#include <vector>
int main() {
    int n,boundary; std::cin >> n >> boundary;
    std::vector<int> a(n);
    for (int& x : a) std::cin >> x;
    auto position=std::lower_bound(a.begin(),a.end(),boundary);
    std::cout << std::distance(a.begin(),position) << '\n';
}
''','std::lower_bound(a.begin(),a.end(),boundary)','std::upper_bound(a.begin(),a.end(),boundary)',['Lỗi logic'],
    'lower_bound_equality_condition',
    'Lệnh upper_bound trong main bỏ qua các phần tử bằng boundary nên không tìm vị trí đầu tiên lớn hơn hoặc bằng.',
    'Dùng std::lower_bound để vị trí trả về bao gồm trường hợp bằng boundary.',
    'lower_bound trả đúng vị trí đầu tiên có giá trị lớn hơn hoặc bằng boundary.',
    'Dãy không giảm đáp ứng tiền điều kiện của lower_bound. Nếu không có phần tử phù hợp hoặc dãy rỗng, iterator bằng end và khoảng cách từ begin bằng n; với giá trị trùng, hàm trả vị trí đầu của nhóm phù hợp.')
    add(38,r'''
#include <array>
#include <iostream>
int main() {
    int n,target; std::cin >> n >> target;
    std::array<int,201> prior{};
    int pairs=0;
    while (n--) {
        int value; std::cin >> value;
        int wanted=target-value;
        if (-100<=wanted && wanted<=100) pairs+=prior.at(wanted+100);
        ++prior.at(value+100);
    }
    std::cout << pairs << '\n';
}
''',r'''        if (-100<=wanted && wanted<=100) pairs+=prior.at(wanted+100);
        ++prior.at(value+100);''',r'''        ++prior.at(value+100);
        if (-100<=wanted && wanted<=100) pairs+=prior.at(wanted+100);''',['Lỗi logic'],
    'prior_frequency_order',
    'Việc tăng prior trước khi đếm khiến phần tử hiện tại có thể ghép với chính nó, trái điều kiện hai chỉ số khác nhau.',
    'Cộng tần suất của phần bù trước rồi mới thêm phần tử hiện tại vào prior.',
    'prior chỉ chứa các phần tử đứng trước khi đếm cặp với phần tử hiện tại.',
    'Tần suất của phần bù cho số cặp kết thúc ở vị trí đang đọc. Chỉ cập nhật prior sau bước đếm nên mỗi cặp có hai chỉ số khác nhau và được tính đúng một lần; kiểm tra miền phần bù trước khi truy cập giữ chỉ số hợp lệ.')
    add(39,r'''
#include <iostream>
int main() {
    int n; std::cin >> n;
    int negatives=0;
    bool has_zero=false;
    while (n--) {
        int value; std::cin >> value;
        negatives+=(value<0);
        has_zero=has_zero || value==0;
    }
    std::cout << (has_zero?0:(negatives%2?-1:1)) << '\n';
}
''','negatives%2?-1:1','negatives%2?1:-1',['Lỗi logic'],
    'product_sign_parity',
    'Biểu thức xuất trong main đảo hai dấu tương ứng với số lượng phần tử âm chẵn và lẻ.',
    'Trả dấu âm khi negatives lẻ và dấu dương khi negatives chẵn nếu không có số không.',
    'Chương trình ưu tiên tích bằng không rồi xác định dấu bằng tính chẵn lẻ của số phần tử âm.',
    'has_zero lưu việc từng gặp số không nên các phần tử sau không thể làm mất trạng thái tích bằng không. Khi không có số không, mỗi số âm đổi dấu đúng một lần; đếm chẵn lẻ tránh cần nhân toàn bộ dãy và tránh tràn tích.')
    add(40,r'''
#include <cstdlib>
#include <iostream>
long long common(long long a,long long b) {
    if (a==0) return b;
    return common(b%a,a);
}
int main() {
    long long numerator,denominator; std::cin >> numerator >> denominator;
    bool negative=(numerator<0)!=(denominator<0);
    long long top=std::llabs(numerator),bottom=std::llabs(denominator);
    long long divisor=common(top,bottom);
    top/=divisor; bottom/=divisor;
    if (negative) top=-top;
    std::cout << top << ' ' << bottom << '\n';
}
''','bool negative=(numerator<0)!=(denominator<0);','bool negative=(numerator<0)&&(denominator<0);',['Lỗi logic'],
    'fraction_sign_xor',
    'Biến negative dùng phép và hai dấu âm nên xác định sai dấu của phân số khi chuẩn hóa mẫu dương.',
    'Đặt negative đúng khi hai dấu khác nhau bằng phép so sánh khác giữa hai điều kiện âm.',
    'Dấu được tách riêng theo hai dấu khác nhau trước khi rút gọn các độ lớn.',
    'common tìm UCLN của hai độ lớn và cả tử lẫn mẫu được chia cho cùng ước. Mẫu kết quả luôn dương; dấu âm chỉ gắn lại ở tử khi hai dấu ban đầu khác nhau. Nếu tử bằng không, UCLN bằng độ lớn mẫu nên mẫu rút về một.')
    add(42,r'''
#include <iostream>
long long days_before(int year) {
    long long previous=year-1;
    return previous*365 + previous/4 - previous/100 + previous/400;
}
int main() {
    int year; std::cin >> year;
    bool leap=days_before(year+1)-days_before(year)==366;
    std::cout << (leap?"YES":"NO") << '\n';
}
''','previous*365 + previous/4 - previous/100 + previous/400','previous*365 + previous/4 + previous/100 + previous/400',['Lỗi logic'],
    'gregorian_century_correction',
    'Công thức days_before cộng phần previous/100 thay vì trừ nên số ngày năm tròn thế kỷ bị tính sai.',
    'Trừ previous/100 và giữ phần cộng previous/400 trong công thức đếm ngày.',
    'days_before điều chỉnh đúng các năm chia hết cho một trăm và bốn trăm.',
    'Công thức cộng các ngày thường rồi thêm ngày nhuận theo từng chu kỳ, loại năm tròn thế kỷ và khôi phục ngoại lệ chia hết cho bốn trăm. Hiệu giữa đầu hai năm liên tiếp là số ngày của năm đang xét, nên kiểm tra số ngày nhuận tương đương quy tắc Gregorian trong đề.')
    add(47,r'''
#include <algorithm>
#include <iostream>
#include <utility>
#include <vector>
int choose(const std::vector<std::pair<int,int>>& items,int index,int space) {
    if (index==(int)items.size()) return 0;
    int answer=choose(items,index+1,space);
    if (items[index].first<=space)
        answer=std::max(answer,items[index].second+choose(items,index+1,space-items[index].first));
    return answer;
}
int main() {
    int n,capacity; std::cin>>n>>capacity;
    std::vector<std::pair<int,int>> items(n);
    for (auto& item : items) std::cin>>item.first>>item.second;
    std::cout<<choose(items,0,capacity)<<'\n';
}
''','choose(items,index+1,space-items[index].first)','choose(items,index,space-items[index].first)',['Lỗi thuật toán'],
    'zero_one_item_progress',
    'Nhánh lấy món trong choose giữ nguyên index nên cùng món có thể được lấy nhiều lần.',
    'Chuyển sang index+1 ở cả nhánh lấy món để mỗi món chỉ được xét một lần.',
    'Cả hai nhánh của choose đều chuyển sang món tiếp theo nên không dùng lại món đã xét.',
    'Mỗi lời gọi so sánh phương án bỏ món với phương án lấy món nếu còn đủ chỗ. Hai nhánh cùng tiến index, nên duyệt mọi tập con hợp lệ và mỗi món được lấy tối đa một lần; số món trong đề cho phép cách liệt kê này.')
    add(48,r'''
#include <iostream>
#include <vector>
long long count_choices(const std::vector<int>& coins,int type,int remaining) {
    if (type==(int)coins.size()) return remaining==0;
    long long ways=0;
    int limit=remaining/coins[type];
    for (int quantity=0; quantity<=limit; ++quantity)
        ways+=count_choices(coins,type+1,remaining-quantity*coins[type]);
    return ways;
}
int main() {
    int n,total; std::cin>>n>>total;
    std::vector<int> coins(n);
    for (int& coin : coins) std::cin>>coin;
    std::cout<<count_choices(coins,0,total)<<'\n';
}
''','int limit=remaining/coins[type];','int limit=(remaining>=coins[type] ? 1 : 0);',['Lỗi thuật toán'],
    'unlimited_denomination_quantity',
    'Biến limit trong count_choices chỉ cho dùng tối đa một đồng mỗi loại, trái yêu cầu số lượng không giới hạn.',
    'Đặt limit bằng remaining/coins[type] để xét mọi số lượng dùng được của loại hiện tại.',
    'count_choices xét đủ mọi số lượng của từng mệnh giá mà không phân biệt thứ tự đồng tiền.',
    'Mỗi mức đệ quy chốt số lượng của một loại rồi chuyển sang loại tiếp theo. Giới hạn thương bảo đảm tổng không vượt phần còn thiếu và không bỏ số lượng hợp lệ; đến hết loại, chỉ trạng thái còn thiếu bằng không được đếm, gồm cả cách không lấy đồng nào khi tổng bằng không.')
    add(49,r'''
#include <algorithm>
#include <iostream>
#include <utility>
#include <vector>
int main() {
    int n; std::cin>>n;
    std::vector<std::pair<int,int>> spans(n);
    for (auto& span : spans) std::cin>>span.first>>span.second;
    std::sort(spans.begin(),spans.end());
    int begin=0;
    while (begin<n) {
        int left=spans[begin].first,right=spans[begin].second;
        int next=begin+1;
        while (next<n && spans[next].first<=right) {
            right=std::max(right,spans[next].second);
            ++next;
        }
        std::cout<<left<<' '<<right<<' ';
        begin=next;
    }
    std::cout<<'\n';
}
''','spans[next].first<=right','spans[next].first<right',['Lỗi edge case'],
    'closed_interval_contact',
    'Điều kiện vòng gộp loại trường hợp đầu trái bằng right nên tách sai hai đoạn có chung đầu mút.',
    'Cho phép spans[next].first bằng right trong điều kiện gộp.',
    'Điều kiện gộp bao gồm đoạn chỉ tiếp xúc ở đầu mút và giữ đầu phải lớn nhất.',
    'Sau khi sắp đầu trái, vòng trong mở rộng một thành phần giao liên tiếp bằng cách giữ đầu phải lớn nhất. So sánh không nghiêm ngặt tính cả tiếp xúc đầu mút; next luôn tiến, còn input rỗng không tạo đoạn kết quả.')
    add(50,r'''
#include <algorithm>
#include <iostream>
#include <set>
#include <string>
int main() {
    std::string text; std::getline(std::cin,text);
    int best=0;
    for (int begin=0; begin<(int)text.size(); ++begin) {
        std::set<char> used;
        for (int end=begin; end<(int)text.size(); ++end) {
            bool fresh=used.insert(text[end]).second;
            if (!fresh) break;
            best=std::max(best,end-begin+1);
        }
    }
    std::cout<<best<<'\n';
}
''','if (!fresh) break;','if (fresh) break;',['Lỗi logic'],
    'unique_substring_stopping_condition',
    'Vòng trong main dừng khi vừa gặp ký tự mới nên không xét tiếp các đoạn chưa có lặp.',
    'Chỉ dừng khi fresh bằng false, tức ký tự hiện tại đã có trong used.',
    'Vòng trong chỉ dừng khi gặp ký tự trùng trong đoạn đang mở rộng.',
    'Mỗi vị trí đầu có một tập used riêng, và mỗi ký tự được thêm chỉ khi mở rộng đoạn. Trước lần chèn bị trùng, đoạn chứa toàn ký tự khác nhau; lấy lớn nhất qua mọi vị trí đầu cho đáp án, còn dòng rỗng giữ best bằng không.')
    return specs

HARNESS_LINKED=r'''
#include <iostream>
void print_nodes(Node* head) {
    bool first=true;
    for (Node* node=head;node;node=node->next) {
        if (!first) std::cout<<' ';
        first=false;
        std::cout<<node->value;
    }
    std::cout<<'\n';
}
int main() {
    int n,key;std::cin>>n>>key;
    std::vector<int> data(n);
    for (int& x:data)std::cin>>x;
    Node* head=build(data);
    print_nodes(head);
    std::cout<<count_value(head,key)<<'\n'<<maximum(head)<<'\n';
    erase_value(head,key);
    print_nodes(head);
    while (head) {Node* gone=head;head=head->next;delete gone;}
}
'''
HARNESS_RECORD=r'''
int main() {
    int n,threshold;std::cin>>n>>threshold;
    auto records=prob1(std::cin,n);
    bool first=true;
    for (const auto& r:records) {
        if (!first)std::cout<<' ';
        first=false;
        std::cout<<r.name<<' '<<r.score;
    }
    std::cout<<'\n'<<prob2(records)<<'\n'<<prob3(records,threshold)<<'\n';
    prob4(records,threshold);
}
'''

def build_cases(root):
    families={x['family_id']:x for x in json.loads((Path(root)/'data/raw/task3-sft-v1/families.json').read_text())}
    cases=[]
    for number,s in enumerate(author_specs(),1):
        family_id=f"F{s['f']:02}"; family=families[family_id]
        if family['split']!='train':raise ValueError('training author accessed nontrain family')
        pair_id=f'V2T{number:02}'
        tests=[{'input':text,'expected':oracle(family_id,text)} for text in input_cases(s['f'])]
        mutation={'before':s['before'],'after':s['after'],'reason':s['diagnosis']}
        for bad in (False,True):
            code=s['code'].replace(s['before'],s['after'],1) if bad else s['code']
            labels=s['labels'] if bad else []
            prose=[('Bài làm có lỗi cần sửa.' if bad else 'Bài làm đáp ứng yêu cầu của đề.'),s['diagnosis'] if bad else s['clean2'],(s['diagnosis']+' '+s['repair']) if bad else s['clean3'],(s['diagnosis']+' '+s['repair']+' '+s['clean3'] if bad else s['clean3']+' Có thể giữ nguyên chương trình dưới đây.')+'\n\n```cpp\n'+s['code'].rstrip()+'\n```']
            cases.append(dict(sample_id=pair_id+('-D' if bad else '-C'),pair_id=pair_id,family_id=family_id,cluster=family['cluster'],split='train',statement=family['statement'],exam_type=family.get('exam_type','single_problem'),checker=family['checker'],code=code,harness=HARNESS_LINKED if s['f']==10 else HARNESS_RECORD if s['f']==11 else '',labels=labels,intended_defective=bad,expected_failure_kind=s['failure'] if bad else 'none',solution_source_id=pair_id+'-C',mechanism=s['mechanism'],mutation=mutation,invariant=s['clean3'],targets={str(i):{'taxonomy_error':labels,'feedback':p} for i,p in enumerate(prose,1)},tests=tests,oracle_provenance=f'Python specification oracle {Path(__file__).name}:oracle({family_id}); independent of C++ repair; deterministic boundary cases and bounded cases; synthetic agent-authored and agent-reviewed, no independent human gold'))
    assert len(cases)==80 and sum(c['intended_defective'] for c in cases)==40
    return cases

def verify(cases,root,output,sandbox_root):
    """Execute all compiled programs solely through the established confined runner."""
    sys.path.insert(0,str(Path(root)/'src'))
    from task3.cpp_sandbox import CppSandbox
    sandbox=CppSandbox(sandbox_root)
    output=Path(output)
    output.mkdir(parents=True,exist_ok=True)
    records=[]
    for case in cases:
        source=case['code']+case['harness']
        jail,compiled=sandbox.compile(source,output/'temporary-jails')
        try:
            syntax=sandbox._call(jail,['/usr/bin/g++','-std=c++11','-fsyntax-only','-fmax-errors=3','/work/source.cpp'],'',compile_phase=True)
            syntax_path=output/(case['sample_id']+'.syntax-only.json')
            syntax_path.write_text(json.dumps(syntax,ensure_ascii=False,indent=2)+'\n')
            diagnostics=None
            if case['mechanism']=='actual_use_before_initialization':
                diagnostics=sandbox._call(jail,['/usr/bin/g++','-std=c++11','-O2','-Wall','-Wextra','-Wuninitialized','-c','/work/source.cpp','-o','/work/diagnostic.o'],'',compile_phase=True)
            runs=[]
            if compiled['returncode']==0:
                for test in case['tests']:
                    actual=sandbox.run(jail,test['input'])
                    matches=(actual['stdout']==test['expected']) if case['checker']=='exact_bytes' else actual['stdout'].split()==test['expected'].split()
                    passed=actual['returncode']==0 and not actual['timeout'] and matches
                    runs.append(dict(input=test['input'],expected=test['expected'],actual=actual,passed=passed))
            warning_evidence=bool(diagnostics and re.search(r'(may be|is) used uninitialized',diagnostics['stderr']))
            witnessed=compiled['returncode']!=0 or any(not r['passed'] for r in runs) or warning_evidence
            valid=(witnessed if case['intended_defective'] else compiled['returncode']==0 and len(runs)==len(case['tests']) and all(r['passed'] for r in runs))
            record=dict(sample_id=case['sample_id'],source_sha256=hashlib.sha256(case['code'].encode()).hexdigest(),combined_harness_sha256=hashlib.sha256(source.encode()).hexdigest(),compiler=compiled,syntax_only_log=syntax_path.name,authoring_object_diagnostics=diagnostics,runs=runs,witnessed_defect=witnessed if case['intended_defective'] else False,verification_pass=valid,repair_source_id=case['solution_source_id'],repair_verified_as_clean_partner=False,diagnostic_witness=({'kind':'uninitialized_use_diagnostic','observed_stderr':diagnostics['stderr'],'compiler_returncode':diagnostics['returncode']} if warning_evidence and case['intended_defective'] else None),undefined_behavior_note=('An actual uninitialized-use compiler warning is primary evidence. Runtime values are observations only and are not a deterministic C++ output claim.' if case['mechanism']=='actual_use_before_initialization' and case['intended_defective'] else None),scope='finite bounded specification tests, no proof of correctness; compiler/runtime evidence is private and excluded from prompts')
            (output/(case['sample_id']+'.private.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
            records.append(record)
            print(case['sample_id'], 'PASS' if valid else 'FAIL',len(runs),'bounded cases',flush=True)
        finally:shutil.rmtree(jail)
    clean_verified={r['sample_id'] for r in records if not r['witnessed_defect'] and r['verification_pass']}
    for record in records:
        record['repair_verified_as_clean_partner']=record['repair_source_id'] in clean_verified
        (output/(record['sample_id']+'.private.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
    summary=dict(source_count=len(cases),target_count=len(cases)*4,clean_count=sum(not c['intended_defective'] for c in cases),faulty_count=sum(c['intended_defective'] for c in cases),verification_pass_count=sum(r['verification_pass'] for r in records),repair_pass_count=sum(r['repair_verified_as_clean_partner'] for r in records),bounded_runtime_cases=sum(len(r['runs']) for r in records),clean_sources_verified=sum(not c['intended_defective'] and r['verification_pass'] for c,r in zip(cases,records)),faulty_sources_with_observed_runtime_failure=sum(c['intended_defective'] and c['expected_failure_kind']!='uninitialized_use_diagnostic' and any(not t['passed'] for t in r['runs']) for c,r in zip(cases,records)),faulty_sources_with_link_failure=sum(c['intended_defective'] and c['expected_failure_kind']=='link_error' and r['compiler']['returncode']!=0 for c,r in zip(cases,records)),faulty_sources_with_uninitialized_diagnostic=sum(c['expected_failure_kind']=='uninitialized_use_diagnostic' and r['diagnostic_witness'] is not None for c,r in zip(cases,records)),mechanisms=dict(Counter(c['mechanism'] for c in cases if c['intended_defective'])),failed=[r['sample_id'] for r in records if not r['verification_pass']],limits='Finite deterministic tests; synthetic agent author/review; existing family identities and some standard algorithm patterns overlap intentionally; no independent human gold. Uninitialized-use runtime observations are not a deterministic witness.')
    (output/'SUMMARY.private.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    if summary['failed'] or summary['repair_pass_count']!=80:raise RuntimeError(summary)
    return summary

def write_compatible_evidence(cases,output):
    """Aggregate existing evidence without rerunning C++ or altering observations."""
    output=Path(output); execution={}
    for case in cases:
        record=json.loads((output/(case['sample_id']+'.private.json')).read_text())
        if record['source_sha256']!=hashlib.sha256(case['code'].encode()).hexdigest():
            raise ValueError('evidence source mismatch: '+case['sample_id'])
        syntax=json.loads((output/record['syntax_only_log']).read_text())
        execution[case['sample_id']]={**record,'syntax_only':syntax,'expected_failure_kind':case['expected_failure_kind'],'primary_evidence_kind':('uninitialized_use_diagnostic' if case['expected_failure_kind']=='uninitialized_use_diagnostic' else case['expected_failure_kind'])}
    summary=json.loads((output/'SUMMARY.private.json').read_text())
    summary.pop('faulty_sources_with_only_uninitialized_diagnostic',None)
    summary.update(
        clean_sources_verified=sum(not c['intended_defective'] and execution[c['sample_id']]['verification_pass'] for c in cases),
        faulty_sources_with_observed_runtime_failure=sum(c['intended_defective'] and c['expected_failure_kind']!='uninitialized_use_diagnostic' and any(not t['passed'] for t in execution[c['sample_id']]['runs']) for c in cases),
        faulty_sources_with_link_failure=sum(c['expected_failure_kind']=='link_error' and execution[c['sample_id']]['compiler']['returncode']!=0 for c in cases),
        faulty_sources_with_uninitialized_diagnostic=sum(c['expected_failure_kind']=='uninitialized_use_diagnostic' and execution[c['sample_id']]['diagnostic_witness'] is not None for c in cases),
        uninitialized_runtime_policy='Runtime outcomes of the uninitialized mutant are preserved as observations, excluded from deterministic wrong-answer/failure counts; the actual compiler diagnostic is its primary evidence.',
        repair_verification={c['sample_id']:{'repair_source_id':c['solution_source_id'],'passed':execution[c['solution_source_id']]['verification_pass'],'bounded_oracle_cases':len(execution[c['solution_source_id']]['runs'])} for c in cases},
        passed=all(r['verification_pass'] and r['repair_verified_as_clean_partner'] for r in execution.values()))
    (output/'SUMMARY.private.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    (output/'execution.private.json').write_text(json.dumps(execution,ensure_ascii=False,indent=2)+'\n')
    return summary

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--verify',action='store_true')
    parser.add_argument('--refresh-evidence',action='store_true')
    parser.add_argument('--sandbox-root',type=Path,default=Path('/workspace/llm-final-project/outputs/task3/round23-20261022/sandbox-template'))
    args=parser.parse_args();cases=build_cases(args.root)
    destination=args.root/'data/raw/task3-sft-v2-authoring/train-new.private.json'
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(cases,ensure_ascii=False,indent=2)+'\n')
    if args.verify:
        verify(cases,args.root,destination.parent/'train-verification',args.sandbox_root)
        print(json.dumps(write_compatible_evidence(cases,destination.parent/'train-verification'),ensure_ascii=False))
    elif args.refresh_evidence:
        print(json.dumps(write_compatible_evidence(cases,destination.parent/'train-verification'),ensure_ascii=False))
    else:print(json.dumps({'path':str(destination),'sources':len(cases),'targets':4*len(cases)},ensure_ascii=False))

if __name__=='__main__':main()
