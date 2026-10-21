#include <iostream>

using namespace std;
const int maxn = 1e4 + 5;

int n, a[maxn];
bool f[maxn];

void inp()
{
    cin >> n;
    for (int i = 1; i <= n; i++)
        cin >> a[i];
}
void solve()
{
    int cnt = 0;
    for (int i = 1; i <= n; i++)
    {
        if (f[i])
            continue;
        cnt++;
        for (int j = i + 1; j <= n; j++)
        {
            if (a[i] == a[j])
                f[j] = true;
        }
    }
    cout << cnt << endl;
    for (int i = 1; i <= n; i++)
    {
        if (f[i] == false)
            cout << a[i] << ' ';
    }
}
int main()
{
    inp();
    solve();
}