#include <iostream>
using namespace std;

int main()
{
    int n;
    cin >> n;
    int a[1000];
    for (int i = 0; i < n; i++)
        cin >> a[i];
    // sap xep noi bot roi dem so lan doi gia tri
    for (int i = 0; i < n - 1; i++)
        for (int j = 0; j < n - 1 - i; j++)
            if (a[j] > a[j + 1])
            {
                int t = a[j];
                a[j] = a[j + 1];
                a[j + 1] = t;
            }
    int cnt = 0;
    for (int i = 0; i < n; i++)
        if (i == 0 || a[i] != a[i - 1])
            cnt++;
    cout << cnt;
    return 0;
}
