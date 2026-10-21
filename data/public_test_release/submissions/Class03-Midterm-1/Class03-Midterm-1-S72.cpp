#include <iostream>
#include <math.h>
using namespace std;

int main()
{
    int n;
    int d = 0;
    int sum = 0;
    cin >> n;

    int m = n;
    int k = n;
    while (m > 0)
    {
        d++;
        m /= 10;
    }

    while (n > 0)
    {
        long tich = n % 10;
        for (int i = 1; i < d; i++)
            tich *= (n % 10);
        sum += tich;
        n /= 10;
    }

    if (k == sum)
        cout << "true";
    else
        cout << "false";
    return 0;
}