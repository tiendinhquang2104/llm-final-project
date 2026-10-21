#include <iostream>
using namespace std;

int main()
{

    long long n;
    cin >> n;
    long long k = n;
    long long l = n;
    long long count = 0, sum = 0;
    while (n > 0)
    {
        count++;
        n /= 10;
    }
    while (k > 0)
    {
        int so = 1;
        long long digit = k % 10;
        for (int i = 1; i <= count; i++)
        {
            so *= digit;
        }
        sum += so;
        k /= 10;
    }

    if (sum == l)
    {
        cout << "True";
    }
    else
    {
        cout << "False";
    }

    return 0;
}
