#include <iostream>
using namespace std;

int main()
{
    long long a, b;
    cin >> a >> b;
    long long res = 1;
    while (b > 0)
    {
        res = res * a;
        b--;
    }
    cout << res;
    return 0;
}
