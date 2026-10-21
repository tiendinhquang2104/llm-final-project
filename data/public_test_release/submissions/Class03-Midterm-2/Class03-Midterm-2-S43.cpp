#include <iostream>
#define ll long long
#define maxn 10005
using namespace std;
ll n, a[maxn], b[maxn], m = 0;
int main()
{
    cin >> n;
    for (ll i = 1; i <= n; i++)
        cin >> a[i];
    for (ll i = 1; i <= n; i++)
    {
        bool kt = 1;
        for (ll j = 0; j < m; j++)
        {
            if (b[j] == a[i])
            {
                kt = 0;
                break;
            }
        }
        if (kt)
            b[m++] = a[i];
    }
    cout << m << '\n';
    for (ll i = 0; i < m; i++)
        cout << b[i] << " ";
    return 0;
}