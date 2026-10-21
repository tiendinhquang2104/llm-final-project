#include <iostream>

using namespace std;

int n, a[15], j = 0;

int count(int n)
{
    int res = 0;
    while (n)
    {
        ++res;
        a[++j] = n % 10;
        n /= 10;
    }
    return res;
}

int pow(int n, int m)
{
    int res = 1;
    for (int i = 1; i <= m; ++i)
        res *= n;
    return res;
}

int main()
{
    cin >> n;
    int num = count(n), res = 0;
    for (int i = 1; i <= num; ++i)
    {
        res += pow(a[i], num);
    }
    cout << (res == n ? "True" : "False");
    return 0;
}