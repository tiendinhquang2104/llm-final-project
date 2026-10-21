#include <iostream>

using namespace std;

// }}
int main()
{
    int count = 1;
    int n;
    cin >> n;
    int a[10000];
    for (int i = 0; i < n; i++)
    {
        cin >> a[i];
    }
    int b[10000] = {a[0]};
    for (int i = 0; i < n; i++)
    {
        int flag = true;
        for (int j = 0; j < count; j++)
        {
            if (b[j] == a[i])
            {
                flag = false;
            }
        }
        if (flag)
        {
            b[count] = a[i];
            count++;
        }
    }
    cout << count << endl;
    for (int i = 0; i < count; i++)
    {
        cout << b[i] << ' ';
    }
}