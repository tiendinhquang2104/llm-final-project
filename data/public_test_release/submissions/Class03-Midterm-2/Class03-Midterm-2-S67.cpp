#include <iostream>

using namespace std;

int remove(int n, int a[])
{
    if (n < 1 || n > 1000000000)
    {
        cout << "Input again";
    }
    int count = 0;
    int b[10000];
    for (int i = 0; i < n; i++)
    {
        for (int j = 0; j < n; j++)
        {
            if (a[i] != b[i])
            {
                b[i] = a[i];
                count++;
            }
            if (a[i] == b[i])
                continue;
        }
    }
    cout << count << endl;
    for (int i = 0; i < n; i++)
    {
        cout << b[i] << " ";
    }

    return 0;
}

int main()
{
    int n;
    cout << "Input array size: ";
    cin >> n;
    int a[10000];
    cout << "Input array: ";
    for (int i = 0; i < n; i++)
    {
        cin >> a[i];
    }
    remove(n, a);
    return 0;
}