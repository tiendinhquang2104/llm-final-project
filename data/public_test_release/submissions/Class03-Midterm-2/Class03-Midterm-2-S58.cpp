#include <iostream>

using namespace std;
int b[10001];
int main()
{
    int n;
    cin >> n;
    int a[n];

    int dem = 0;
    for (int i = 0; i < n; i++)
    {
        cin >> a[i];
        b[a[i]]++;
        if (b[a[i]] <= 1)
        {
            dem++;
        }
    }
    cout << dem << endl;
    for (int i = 0; i < n; i++)
    {
        if (b[a[i]] >= 1)
        {
            cout << a[i] << " ";
            b[a[i]] = 0;
        }
    }
}