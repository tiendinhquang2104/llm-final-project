#include <iostream>
using namespace std;
int main()
{
    int n;
    cin >> n;
    int a[10000];
    for (int i = 0; i < n; i++)
    {
        cin >> a[i];
    }
    int giatri[10000];
    int dem = 0;
    for (int i = 0; i < n; i++)
    {
        bool b = false;
        for (int j = 0; j < dem; j++)
        {
            if (a[i] == giatri[j])
            {
                b = true;
                break;
            }
        }
        if (!b)
        {
            giatri[dem] = a[i];
            dem++;
        }
    }
    cout << dem << endl;
    for (int i = 0; i < dem; i++)
    {
        cout << giatri[i];
        if (i < dem - 1)
            cout << " ";
    }
    return 0;
}