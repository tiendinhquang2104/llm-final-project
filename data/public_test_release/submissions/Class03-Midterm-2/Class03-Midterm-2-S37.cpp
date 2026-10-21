#include <iostream>

using namespace std;

const int maxn = 1e5 + 1;
const int maxa = 1e9 + 1;
int n, max_val;
int a[maxn];
int ans[maxn];

void doc()
{
    cin >> n;
    for (int i = 1; i <= n; i++)
    {
        cin >> a[i];
        max_val = max(max_val, a[i]);
    }
}

void sub1()
{

    bool f[maxn];
    int cnt = 0;
    for (int i = 1; i <= n; i++)
    {
        if (!f[a[i]])
        {
            cnt++;
            ans[cnt] = a[i];
            f[a[i]] = true;
        }
    }
    cout << cnt << '\n';
    for (int i = 1; i <= cnt; i++)
        cout << ans[i] << ' ';
}

int main()
{
    doc();
    sub1();
    return 0;
}