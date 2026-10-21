#include <iostream>
#define ll long long
using namespace std;

ll tinhtich(ll n, ll m)
{
    ll a = n;
    for (int i = 2; i <= m; i++)
    {
        m *= n;
    }
    return m;
}
int a[30];

int main()
{
    ll n;
    cin >> n;
    ll sum = 0;
    ll k = 0;
    ll b = n;
    while (n != 0)
    {
        a[k++] = n % 10;
        n /= 10;
    }
    for (ll i = 0; i < k; i++)
    {
        sum += tinhtich(a[i], k);
    }
    if (sum == b)
    {
        cout << "True\n";
    }
    else
    {
        cout << "False\n";
    }
    return 0;
}