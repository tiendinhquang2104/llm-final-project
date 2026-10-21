#include <iostream>
using namespace std;
void Input(long long &n)
{
    cin >> n;
}
void Process(long long n)
{
    long long sum = 0;
    long long k = n;
    long long u = n;
    int count = 0;
    while (u > 0)
    {
        count++;
        u /= 10;
    }
    while (n > 0)
    {
        long long tmp = (n % 10);
        n = n / 10;
        long long k = tmp;
        for (int i = 1; i <= count - 1; i++)
        {
            tmp = k * tmp;
        }
        sum += tmp;
    }
    if (sum == k)
    {
        cout << "True";
    }
    else
    {
        cout << "False";
    }
}
int main()
{
    long long n;
    Input(n);
    Process(n);
    return 0;
}