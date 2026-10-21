#include <iostream>
using namespace std;
int ts(int n)
{
    int dem = 0;
    while (n != 0)
    {
        ++dem;
        n /= 10;
    }
    bool sum(long long n);
    int res = 0, dem = ts(n);
    const int temp = n;
    while (n != 0)
    {
        res = res + (n % 10) * dem;
        n /= 10;
    }
    if (res == temp)
    {
        return true
    }
    else
    {
        return False
    };
}
int main()
{
    long long n;
    cin >> n;
    if (sum(n) == true)
    {
        cout << "True";
    }
    else
    {
        cout << "False";
    }
    return 0;
}
