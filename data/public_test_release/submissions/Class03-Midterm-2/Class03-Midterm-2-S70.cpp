#include <iostream>

using namespace std;

int main()
{
    int n;
    int a[100];
    int b[100];
    cin >> n;
    for (int i = 0; i < n; i++)
    {
        cin >> a[i];
    }
    for (int i = 0; i < n; i++)
    {
        for (int j = i + 1; j < n; j++)
        {
            if (a[i] > a[j])
            {
                int tmp = a[i];
                a[i] = a[j];
                a[j] = a[i];
            }
        }
    }
    for (int i = 0; i < n; i++)
    {
        if (a[i] != a[i + 1])
        {
            b[i] = a[i];
        }
    }

    for (int i = 0; i < n; i++)
    {
        cout << b[i];

        return 0;
    }
}