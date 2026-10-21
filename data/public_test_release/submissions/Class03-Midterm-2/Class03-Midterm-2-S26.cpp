#include <iostream>

using namespace std;

int n, a[10005], idx = 0;

int main()
{
    cin >> n;
    for (int i = 1; i <= n; ++i)
    {
        int x, check = 1;
        cin >> x;
        for (int j = 1; j < i; ++j)
        {
            if (a[j] == x)
            {
                check = 0;
                break;
            }
        }
        if (check)
            a[++idx] = x;
    }
    cout << idx << "\n";
    for (int i = 1; i <= idx; ++i)
    {
        cout << a[i] << " ";
    }
    return 0;
}