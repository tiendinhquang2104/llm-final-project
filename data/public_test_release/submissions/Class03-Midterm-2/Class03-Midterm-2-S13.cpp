#include <iostream>
using namespace std;
const int N = 50;
int msin()
{
    int n;
    cin >> n;
    int arr[N];
    for (int i = 0; i < n; i++)
    {
        cin >> arr[i];
    }
    int k = 0;
    if (k == 1)
    {
        cout << arr[0];
    }
    for (int i = 1; i < n - 1; i++)
    {
        for (int j = i + 1; j < n; j++)
        {
            if (arr[i] == arr[j])
            {
                k++;
            }
        }
    }
    for (int i = 0; i < n; i++)
    {
        cout << arr[i] << " ";
    }
}