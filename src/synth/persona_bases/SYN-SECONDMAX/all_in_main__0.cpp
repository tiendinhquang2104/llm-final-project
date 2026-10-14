#include <iostream>
using namespace std;

int main()
{
    int n;
    cin >> n;
    int a[1000];
    for (int i = 0; i < n; i++)
        cin >> a[i];
    // sap xep giam dan, lay phan tu thu 2
    for (int i = 0; i < n; i++)
        for (int j = i + 1; j < n; j++)
            if (a[j] > a[i])
            {
                int t = a[i];
                a[i] = a[j];
                a[j] = t;
            }
    cout << a[1];
    return 0;
}
