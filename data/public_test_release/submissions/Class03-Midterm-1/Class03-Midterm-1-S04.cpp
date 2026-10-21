#include <iostream>
using namespace std;
using ll = long long;

int powOfD(int num, int d)
{
    int res = 1;
    for (int i = 1; i <= d; i++)
    {
        res *= num;
    }
    return res;
}
ll checkArmstrong(ll n)
{
    ll armCheck = 0;
    int countDigit = 0;
    int copyN = n;
    while (copyN > 0)
    {
        copyN /= 10;
        countDigit++;
    }
    while (n > 0)
    {
        int tmp = n % 10;
        armCheck += ll(powOfD(tmp, countDigit));
        n /= 10;
    }
    return armCheck;
}
int main()
{
    ll n;
    cin >> n;
    if (n == checkArmstrong(n))
    {
        cout << "True";
        return 0;
    }
    else
    {
        cout << "False";
        return 0;
    }
}