#include <iostream>

using namespace std;

bool Armstrong(int n)
{
    int a = n;
    int b = n;
    int tmp;

    long long sum = 0;
    int count = 0;
    while (n)
    {
        count++;
        n /= 10;
    }

    while (a)
    {
        int sumphu = 1;
        tmp = a % 10;
        for (int i = 0; i < count; i++)
        {
            sumphu *= tmp;
        }

        sum += sumphu;
        a /= 10;
    }
    return sum == b;
}
// }}
int main()
{
    int n;
    cin >> n;
    if (Armstrong(n))
        cout << "TRUE";
    else
        cout << "FALSE";

    return 0;
}