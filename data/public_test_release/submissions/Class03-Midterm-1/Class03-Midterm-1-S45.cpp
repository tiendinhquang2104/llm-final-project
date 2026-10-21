#include <iostream>
#define ll long long
using namespace std;
ll nhan(ll n, ll k)
{
    ll p = n;
    for (ll i = 2; i <= k; i++)
        p *= n;
    return p;
}
ll a[12];
int main()
{
    ll n;
    cin >> n;
    ll s = 0, m = 0, x = n;
    while (n != 0)
    {
        a[m++] = n % 10;
        n /= 10;
    }
    for (ll i = 0; i < m; i++)
    {
        s += nhan(a[i], m);
    }
    if (s == x)
        cout << "True";
    else
        cout << "False";
    return 0;
}