#include <iostream>

using namespace std;

long long n;

int tach(long long n)
{
    int cnt = 0;
    while (n)
    {
        cnt++;
        n /= 10;
    }
    return cnt;
}
long long cal_pow(long long x, int cnt)
{
    long long tmp = 1;
    for (int i = 1; i <= cnt; i++)
        tmp *= x;
    return tmp;
}
bool check(long long n)
{
    int cnt = tach(n);
    long long x = n;
    long long s = 0;
    for (int i = 1; i <= cnt; i++)
    {
        long long tmp = cal_pow(x % 10, cnt);
        x /= 10;
        s += tmp;
    }
    return (n == s);
}
int main()
{
    cin >> n;
    if (check(n))
        cout << "True" << endl;
    else
        cout << "False" << endl;
}