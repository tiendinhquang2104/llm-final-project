#include <iostream>
using namespace std;

int main()
{
    int n;
    cin >> n;
    int a[n];
    for (int i = 0; i < n; i++)
        cin >> a[i];

    int b[n];
    int cnt = 0;
    for (int i = 0; i < n; i++)
    {
        bool ck = true;
        for (int j = 0; j < i; j++)
            if (a[j] == a[i])
            {
                ck = false;
                break;
            }
        if (ck)
        {
            b[cnt] = a[i];
            cnt++;
        }
    }

    cout << cnt << '\n';
    for (int i = 0; i < cnt; i++)
        cout << b[i] << ' ';
}