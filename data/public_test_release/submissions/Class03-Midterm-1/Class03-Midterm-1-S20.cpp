#include <iostream>
using namespace std;
long long mpow(int a, int x)
{
    /*if (x == 0)
        return 1;
    if (x == 1)
        return a;
    long long t = mpow(a, x / 2);
    t *= t;
    if (x % 2 == 1)
        return t * a;
    return t;*/
    long long t = 1;
    for (int i = 1; i <= x; i++)
        t *= a;
    return t;
}
long long armo(int a)
{
    long long res = 0;
    int b = a;
    int d = 0;
    while (b > 0)
    {
        b /= 10;
        d++;
    }
    while (a > 0)
    {
        long long t = a % 10;
        a /= 10;
        t = mpow(t, d);
        res += t;
    }
    return res;
}
void check(int a)
{
    if (a == armo(a))
        cout << "True";
    else
        cout << "False";
}
int main()
{
    int a;
    cin >> a;
    check(a);
    return 0;
}