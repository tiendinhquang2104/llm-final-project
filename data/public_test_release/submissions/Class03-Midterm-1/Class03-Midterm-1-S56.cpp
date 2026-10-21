#include <iostream>

using namespace std;

long long myPow(int a, int n)
{
    int res = 1;
    for (int i = 0; i < n; i++)
        res = res * a;
    return res;
}
int cntDigit(int n)
{
    int res = 0;
    while (n % 10 > 0)
    {
        res++;
        n = n / 10;
    }
    return res;
}
bool armstrongNumber(int n)
{
    int m, res = 0;
    int temp = n;
    int d = cntDigit(n);
    while (n % 10 > 0)
    {

        m = (n % 10);
        res = res + myPow(m, d);
        n = n / 10;
    }
    if (res == temp)
        return 1;
    else
        return 0;
}

int main()
{
    int n;
    cin >> n;
    if (armstrongNumber(n))
        cout << "True";
    else
        cout << "False";
    return 0;
}