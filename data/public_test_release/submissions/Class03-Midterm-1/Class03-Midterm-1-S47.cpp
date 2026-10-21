#include <iostream>

using namespace std;
int n, kq = 0;
int main()
{
    cin >> n;
    int n1 = n, dem = 0;
    while (n1 != 0)
    {
        dem++;
        n1 /= 10;
    }
    n1 = n;
    int a = 1;
    while (n1 != 0)
    {
        for (int i = 1; i <= dem; i++)
            a = a * (n1 % 10);
        kq += a;
        n1 /= 10;
        a = 1;
    }
    if (kq == n)
        cout << "True";
    else
        cout << "False";
    return 0;
}
