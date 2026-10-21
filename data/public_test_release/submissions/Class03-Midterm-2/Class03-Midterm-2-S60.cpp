#include <iostream>
using namespace std;
int main()
{

    int n;
    cin >> n;
    int count = 0;
    int a[1000];
    for (int i = 0; i < n; i++)
    {
        cin >> a[i];
    }

    for (int i = 0; i < n - 1; i++)
    {
        for (int j = i + 1; j < n; j++)
        {
            if (a[i] == a[j])
            {
                count++;
            }
        }
    }
    for (int i = 0; i < n; i++)
    {
        if (count == n)
        {
            cout << a[i];
            break;
        }
    }

    return 0;
}