#include <iostream>

using namespace std;

int dem(int n)
{
    int d;
    while (n != 0)
    {
        d++;
        n /= 10;
    }
    return d;
}
int tong(int n)
{
    int a, tong = 0;
    cin >> n;
    while (n != 0)
    {
        a = n % 10;
        for (int i = 2; i <= dem(n); i++)
            a *= a;
        n /= 10;
        tong += a;
    }
    return tong;
}

int main()
{
    int m;
    cin >> m;
    if (m == tong(m))
        cout << "True";
    else
        cout << "False";

    return 0;
}