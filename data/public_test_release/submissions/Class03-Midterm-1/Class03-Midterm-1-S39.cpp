#include <iostream>

using namespace std;

int n;

long long power(long long a, int b)
{
    if (b == 0)
        return 1ll;
    if (b % 2 == 0)
        return power(a, b / 2) * power(a, b / 2);
    else
        return a * power(a, (b - 1));
}

void xuli()
{
    cin >> n;
    int tmp = n;
    int len = 0;
    long long sum = 0;
    while (tmp)
    {
        len++;
        tmp /= 10;
    }
    tmp = n;
    while (tmp)
    {
        sum += power(tmp % 10, len);
        // cout << power(tmp % 10, len) << ' ';
        tmp /= 10;
    }

    if (sum == n)
        cout << "True\n";
    else
        cout << "False";
}

int main()
{
    xuli();
    return 0;
}