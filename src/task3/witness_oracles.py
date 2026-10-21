"""Hidden scoring oracles for explicit train-derived scoped domains.

These functions are NEVER imported by the inference runner. They independently
compute task results, not mutant behavior, and refuse out-of-domain witnesses.
"""
from __future__ import annotations
import math
import re
from functools import reduce
CSV_FAMILIES={'SYN-GEN','SYN-PROD','SYN-SUMPAIR','SYN-SUMB','SYN-MINA','SYN-COUNTGT','SYN-RANGE'}
ARRAY_FAMILIES={'SYN-SUMEVEN','SYN-MAXARR','SYN-SECONDMAX','SYN-DISTINCT','SYN-GCDARR'}
STRING_FAMILIES={'SYN-COUNTUPPER','SYN-COUNTVOWEL','SYN-REVSTR'}


def oracle(family,witness):
    if not isinstance(witness,dict)or not isinstance(witness.get('stdin'),str)or not isinstance(witness.get('files'),dict):raise ValueError('stdin string and files mapping required')
    text=witness['stdin'];files=witness['files']
    if family in CSV_FAMILIES:
        if text.strip()or set(files)!={'data.csv'}or not isinstance(files['data.csv'],str):raise ValueError('CSV uses only data.csv and empty stdin')
        rows=[]
        for line in files['data.csv'].strip().splitlines():
            if not re.fullmatch(r'\s*-?\d+\s*,\s*-?\d+\s*',line):raise ValueError('CSV row a,b required')
            a,b=map(int,line.split(','))
            if not(-9<=a<=9 and -9<=b<=9):raise ValueError('CSV values outside -9..9')
            rows.append((a,b))
        if not 1<=len(rows)<=6:raise ValueError('CSV row count 1..6')
        result={'SYN-GEN':lambda:sum(a for a,b in rows),'SYN-PROD':lambda:sum(a*b for a,b in rows),
                'SYN-SUMPAIR':lambda:sum(a+b for a,b in rows),'SYN-SUMB':lambda:sum(b for a,b in rows),
                'SYN-MINA':lambda:min(a for a,b in rows),'SYN-COUNTGT':lambda:sum(a>b for a,b in rows),
                'SYN-RANGE':lambda:sum(a<b for a,b in rows)}[family]()
        return str(result)
    if files:raise ValueError('stdin task has no input files')
    tokens=text.split()
    if family in STRING_FAMILIES:
        if len(tokens)!=1 or not 1<=len(tokens[0])<=6:raise ValueError('one string length1..6')
        s=tokens[0]
        alphabet='abcdefghijklmnopqrstuvwxyz'if family=='SYN-COUNTVOWEL'else 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        if any(c not in alphabet for c in s):raise ValueError('ASCII domain')
        return str(sum('A'<=c<='Z'for c in s))if family=='SYN-COUNTUPPER'else str(sum(c in 'aeiou'for c in s))if family=='SYN-COUNTVOWEL'else s[::-1]
    if not tokens or any(not re.fullmatch(r'-?\d+',t)for t in tokens):raise ValueError('integer input required')
    numbers=list(map(int,tokens))
    if family in ARRAY_FAMILIES:
        n,*a=numbers
        if len(a)!=n or not 1<=n<=6:raise ValueError('n and exactly n numbers, 1..6')
        lo,hi=(1,20)if family=='SYN-GCDARR'else(-9,9)
        if any(not lo<=x<=hi for x in a):raise ValueError('array values out of domain')
        if family=='SYN-SECONDMAX'and(n<2 or len(set(a))!=n):raise ValueError('second max requires >=2 distinct')
        return str({'SYN-SUMEVEN':lambda:sum(x for x in a if x%2==0),'SYN-MAXARR':lambda:max(a),
                    'SYN-SECONDMAX':lambda:sorted(a)[-2],'SYN-DISTINCT':lambda:len(set(a)),
                    'SYN-GCDARR':lambda:reduce(math.gcd,a)}[family]())
    if family=='SYN-POWER':
        if len(numbers)!=2 or not(0<=numbers[0]<=3 and 0<=numbers[1]<=6)or numbers==[0,0]:raise ValueError('power a0..3,b0..6')
        return str(pow(*numbers))
    if len(numbers)!=1:raise ValueError('one integer required')
    n=numbers[0]
    bounds={'SYN-PALIN':(0,9999),'SYN-PRIME':(-2,40),'SYN-PERFECT':(1,40),'SYN-FACT':(0,10),
            'SYN-FIB':(0,20),'SYN-DIGITSUM':(0,999),'SYN-ARM':(1,9999),'SYN-BASE2':(0,63)}
    if family not in bounds:raise ValueError('unknown train family')
    lo,hi=bounds[family]
    if not lo<=n<=hi:raise ValueError('scalar outside scoped domain')
    if family=='SYN-PALIN':result=str(n)==str(n)[::-1]
    elif family=='SYN-PRIME':result=n>=2 and all(n%d for d in range(2,math.isqrt(max(n,0))+1))
    elif family=='SYN-PERFECT':result=sum(d for d in range(1,n)if n%d==0)==n
    elif family=='SYN-FACT':return str(math.factorial(n))
    elif family=='SYN-FIB':
        a,b=0,1
        for _ in range(n):a,b=b,a+b
        return str(a)
    elif family=='SYN-DIGITSUM':return str(sum(map(int,str(n))))
    elif family=='SYN-ARM':result=sum(int(x)**len(str(n))for x in str(n))==n
    else:return format(n,'b')
    return 'True'if result else 'False'
