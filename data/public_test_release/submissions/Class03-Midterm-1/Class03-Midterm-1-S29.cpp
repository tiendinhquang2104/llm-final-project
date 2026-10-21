#include <iostream>
using namespace std;
int len(long long n)
{
    int cnt = 0;
    while(n != 0)
    {
        cnt++;
        n /= 10;
    }
    return cnt;
}
int main()
{
    long long n, m;
    cin >> n;
    m = n;
    int cnt = len(n);
    long long sum = 0;
    while(n != 0 )
    {
        int digit = n % 10;
        long long p = 1;
        for ( int i = 1; i <= cnt; i++ )
            p *= digit;
        sum += p;
        n /= 10;
    }
    if (sum == m) cout << "True";
    else cout << "False";
    return 0;
}
