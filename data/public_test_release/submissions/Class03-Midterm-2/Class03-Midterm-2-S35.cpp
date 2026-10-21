#include <iostream>

using namespace std;

int main()
{
    int n;
    cin >> n;
    int a[10000], b[10000];
    for (int i = 0; i < n; i++)
        cin >> a[i];
    int m = 0;
    for (int i = 0; i < n; i++)
    {
        bool found = false;
        for (int j = 0; j < m; j++)
        {
            if (a[i] == b[j])
            {
                found = true;
                break;
            }
        }
        if (!found)
        {
            b[m] = a[i];
            m++;
        }
    }
    cout << m << endl;
    for (int i = 1; i < m; i++)
        cout << b[i] << " ";
    cout << endl;
    return 0;
}