#include <iostream>
using namespace std;
void nhap(int a[100000], int &n)
{
    cin >> n;
    if (n < 1 || n > 10000)
    {
        return;
    }
    else
    {
        for (int i = 0; i <= n; i++)
        {
            cin >> a[i];
        }
    }
}

void xuat(int a[10000], int n)
{
    int dem = 1;
    for (int i = 0; i < n; i++)
    {
        if (a[i] == a[i + 1])
        {
                }
    }
    cout << dem << "\n";
    for (int i = 1; i <= dem; i++)
    {
        cout << a[i] << " " << "\n";
    }
}
int main()
{
    int n;
    cin >> n;
    int a[1000000];
    nhap(a, n);
    xuat(a, n);
    return 0;
}