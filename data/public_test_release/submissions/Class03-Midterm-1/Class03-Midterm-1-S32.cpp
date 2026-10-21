#include <iostream>
using namespace std;
int main()
{
    long long n;
    cin >> n;
    long long temp = n;
    int d = 0;
    while (temp > 0)
    {
        d++;
        temp /= 10;
    }
    temp = n;
    long long sum = 0;
    while (temp > 0)
    {
        int SOCHUSO = temp % 10;
        long long a = 1;
        for (int i = 0; i < d; i++)
        {
            a *= SOCHUSO;
        }
        sum += a;
        temp /= 10;
    }
    if (sum == n)
    {
        cout << "True";
    }
    else
    {
        cout << "False";
    }
    return 0;
}