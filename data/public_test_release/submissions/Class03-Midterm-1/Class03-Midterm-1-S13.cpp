#include <iostream>
using namespace std;

int CheckLength(int n)
{
    int cnt = 0;
    while (n)
    {
        cnt++;
        n /= 10;
    }
    return cnt;
}

int Pow(int a, int n)
{
    int res = 1;
    for (int i = 1; i <= n; i++)
        res *= a;
    return res;
}

int main()
{
    int n;
    cin >> n;
    int len = CheckLength(n);
    int ans = 0;

    int m = n;
    while (m)
    {
        ans += Pow(m % 10, len);
        m /= 10;
    }

    if (ans == n)
        cout << "True";
    else
        cout << "False";
}