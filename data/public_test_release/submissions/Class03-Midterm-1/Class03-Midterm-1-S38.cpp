#include <iostream>
using namespace std;
int main()
{
    int n;
    cin >> n;
    int sum = 0;
    int digits = 0;
    int d = n;
    int count = 0;
    while (d != 0)
    {
        n /= 10;
        count++;
    }
    d = n;
    while (d > 0)
    {
        digits = d % 10;
        d /= 10;
        sum += (digits * digits);
    }
    if (sum == n)
        cout << "True";
    else
        cout << "False";
    return 0;
}
