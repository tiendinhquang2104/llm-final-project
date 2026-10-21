#include <iostream>
#define N 10009
using namespace std;

int n, a[N], b[N], cnt, c[N], p[N], tam[N];

void swap(int &a, int &b)
{
    int t = a;
    a = b;
    b = t;
}

int Find_firstpos(int k)
{
    int t;
    for (int u = 1; u <= n; u++)
    {
        if (k == tam[u])
        {
            t = u;
            break;
        }
    }
    return t;
}

int main()
{
    cin >> n;
    for (int i = 1; i <= n; i++)
    {
        cin >> a[i];
        tam[i] = a[i];
        c[i] = i;
    }
    for (int i = 1; i < n; i++)
    {
        for (int j = i + 1; j <= n; j++)
        {
            if (a[i] > a[j])
            {
                swap(a[i], a[j]);
                swap(c[i], c[j]);
            }
        }
    }

    cnt = 0;
    for (int i = 1; i <= n; i++)
    {
        if (a[i] == a[i + 1])
            continue;
        else
        {
            cnt++;
            b[cnt] = a[i];
        }
    }

    for (int i = 1; i <= cnt; i++)
        p[i] = Find_firstpos(b[i]);

    for (int i = 1; i < cnt; i++)
    {
        for (int j = i + 1; j <= cnt; j++)
        {
            if (p[i] > p[j])
            {
                swap(p[i], p[j]);
                swap(b[i], b[j]);
            }
        }
    }

    cout << cnt << endl;
    for (int i = 1; i <= cnt; i++)
        cout << b[i] << " ";
    return 0;
}
