#include <iostream>
using namespace std;
int Armstrong(int n)
{
    int sum = 0, temp = n, digits = 0, tich = 1;
    while (temp != 0)
    {
        temp /= 10;
        digits++;
    }
    temp = n;
    int tam = digits;
    while (temp != 0)
    {
        while (tam > 0)
        {
            int digit = temp % 10;
            tich *= digit;
            tam--;
        }

        sum += tich;

        tich = 1;
        tam = digits;
        temp /= 10;
    }
    return (sum == n);
}
int main()
{
    long long n;

    cin >> n;
    if (Armstrong(n))
        cout << " True" << endl;
    else
        cout << " False" << endl;
    return 0;
}