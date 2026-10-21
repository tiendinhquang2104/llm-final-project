#include <iostream>
using namespace std;
const int N = 1e4 + 7;
void check1(int a[], int n)
{
    int b[N];
    int m = 0;
    for (int i = 1; i <= n; i++)
    {
        bool ok = 1;
        for (int j = 1; j <= m; j++)
        {
            if (a[i] == b[j])
            {
                ok = 0;
                break;
            }
        }
        if (ok)
        {
            m++;
            b[m] = a[i];
        }
    }
    cout << m << '\n';
    for (int i = 1; i <= m; i++)
        cout << b[i] << ' ';
}
int a[N], n;
int main()
{
    cin >> n;
    for (int i = 1; i <= n; i++)
    {
        cin >> a[i];
    }
    check1(a, n);
    return 0;
}