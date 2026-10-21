#include <iostream>

using namespace std;

void check(int n)
{

    if (n < 1 || n > 1000000000)
    {
        cout << "Input again";
    }
    int m = n;
    int t = 0;

    while (m > 0)
    {
        m = m / 10;
        t++;
    }

    int a[9];
    int p = n;
    for (int i = 0; i < t; i++)
    {
        a[i] = p % 10;
        p = p / 10;
    }

    for (int i = 0; i < t; i++)
    {
        for (int j = 0; j < t; j++)
        {
            a[i] *= a[i];
        }
    }

    int sum = 0;

    for (int i = 0; i < t; i++)
    {
        sum += a[i];
    }

    if (sum == n)
    {
        cout << "True";
    }
    else
        cout << "False";
}

int main()
{
    int n;
    cout << "Input n: ";
    cin >> n;

    check(n);

    return 0;
}