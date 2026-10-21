#include <iostream>
#define ll long long
using namespace std;

int n;

ll LuyThua(int a, int b)
{
    ll res = 1;
    for (int i = 1; i <= b; i++)
    {
        res *= a;
    }
    return res;
}

bool check(int n)
{
    int sum = 0, cnt = 0, t, tam1 = n, tam2 = n;
    while (tam1 > 0)
    {
        tam1 /= 10;
        cnt++;
    }

    while (tam2 > 0)
    {
        t = tam2 % 10;
        tam2 /= 10;
        sum += LuyThua(t, cnt);
    }
    if (sum == n)
        return true;
    return false;
}

int main()
{
    cin >> n;
    if (check(n))
        cout << "True";
    else
        cout << "False";
    return 0;
}