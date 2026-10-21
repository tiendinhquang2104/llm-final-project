#include <iostream>

using namespace std;

#define int long long
int n;
int LENGTH(int n)
{
    int cnt = 0;
    while (n)
    {
        cnt++;
        n /= 10;
    }
    return cnt;
}
int POWMOD(int a, int b)
{
    if (b == 0)
        return 1;
    if (b == 1)
        return a;
    int half = POWMOD(a, b / 2);
    if (b % 2 == 0)
        return half * half;
    else
        return half * half * a;
}

bool check(int n)
{
    int tmp = n, ans = 0;
    while (n > 0 )
    {
        int x = POWMOD( n % 10 ,LENGTH(tmp) ) ;
        ans += x;
        n /= 10 ;
    }

    if (ans == tmp)
        return true;
    return false;
}

main()
{

    //cout << POWMOD(2, 3) << '\n';
    cin >> n;
    //cout << LENGTH(n) << '\n';
    if (check(n) == true)
        cout << "True" << '\n';
    else
        cout << "False" << '\n';
}
