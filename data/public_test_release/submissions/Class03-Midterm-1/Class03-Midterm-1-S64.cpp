#include <iostream>
using namespace std;

int main()
{
    int n;
    cin >> n;
    int temp = n;
    int a = n;
    int tong = 0;
    int dem = 0;
    while (a)
    {
        a = n / 10;
        dem++;
    }
    while (n)
    {
        int q = 1;
        int i = n % 10;
        for (int j = 1; j <= 4; j++)
        {
            q *= i;
        }
        tong += q;
        n /= 10;
    }
    if (tong == temp)
        cout << "DUNG VAY";
    else
        cout << "SAI";
}