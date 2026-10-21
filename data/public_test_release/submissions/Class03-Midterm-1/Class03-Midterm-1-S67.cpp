#include <iostream>

using namespace std;

int counter(long long n) 
{
    int cnt = 0;
    while (n > 0)
    {
        ++cnt;
        n /= 10;
    }
    return cnt;
}
long long process(long long n)
{
    int cnt = counter(n);
    long long res = 0;
    while (n > 0)
    {
        long long tmp = n % 10;
        for (int i = 1; i < cnt; ++i)
            tmp *= (n % 10);
        res += tmp;
        n /= 10;
    }
    return res;
}
int main()
{
    long long n;
    cin >> n;
    if (process(n) == n) cout << "True"; else cout << "False";
}
