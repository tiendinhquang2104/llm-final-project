#include <iostream>
using namespace std;
#define N 50
int main()
{
    int a[N], b[N], n, m;
    cin >> n;
    for (int i = 0; i < n; i++)
    {
        cin >> a[i];
    }
    b[0] = a[0];
    m = 1;
    for (int i = 1; i < n; i++)
    {
        bool same = false;
        for (int j = 0; j < i; j++)
        {
            if (a[i] == a[j])
            {
                same = true;
                break;
            }
        }
        if (!same)
        {
            b[m] = a[i];
            m++;
        }
    }
    cout << m << endl;
    for (int i = 0; i < m; i++)
    {
        cout << b[i] << " ";
    }
}
