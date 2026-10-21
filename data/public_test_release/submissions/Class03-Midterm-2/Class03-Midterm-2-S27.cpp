#include <iostream>
using namespace std;
int main()
{
    int n;
    cin >> n;
    int a[n + 2];
    for (int i = 1; i <= n; i++ ) cin >> a[i];
    int b[n + 2];
    int j = 0;

    for (int i = 1; i <= n; i++)
    {
        bool get = true;
        for (int k = 1; k <= j; k++)
            if (a[i] == b[k])
            {
                get = false;
                break;
            }
        if (get == true)
        {
            j++;
            b[j] = a[i];
        }
    }
    cout << j << endl;
    for ( int i = 1; i <= j; i++ )
        cout << b[i] << " ";
    return 0;
}
