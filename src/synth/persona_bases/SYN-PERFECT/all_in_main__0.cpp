#include <iostream>
using namespace std;

int main()
{
    int n;
    cin >> n;
    long long s = 0;
    for (int i = 1; i <= n / 2; i++)
    {
        if (n % i == 0)
            s += i;
    }
    if (s == n && n > 1)
        cout << "True";
    else
        cout << "False";
    return 0;
}
