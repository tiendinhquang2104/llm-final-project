#include <iostream>
using namespace std;

int main()
{
    int n;
    cin >> n;
    int t = n, d = 0;
    while (t > 0)
    {
        d++;
        t /= 10;
    }
    long long sum = 0;
    t = n;
    while (t > 0)
    {
        int c = t % 10;
        long long p = 1;
        for (int k = 0; k < d; k++)
            p *= c;
        sum += p;
        t /= 10;
    }
    if (sum == n)
        cout << "True" << endl;
    else
        cout << "False" << endl;
    return 0;
}
