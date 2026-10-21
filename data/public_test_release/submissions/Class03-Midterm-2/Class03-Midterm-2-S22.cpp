#include <iostream>
using namespace std;
int main()
{
    int n;
    cin >> n;
    int max = 0;
    int mang[n];
    int mang1[10000] = {0};
    for (int i = 0; i < n; i++)
    {
        cin >> mang[i];
    }
    for (int i = 0; i < n; i++)
    {
        mang1[mang[i]] = mang[i];
    }

    for (int i = 0; i < n; i++)
    {
        if (mang[i] > max)
        {
            max = mang[i];
        }
    }
    for (int i = 0; i <= max; i++)
    {
        if (mang1[i] != 0)
        {
            cout << mang1[i] << " ";
        }
    }
    return 0;
}