#include <iostream>
using namespace std;
#define N 50

void Ams(int arr[N], int brr[N], int &n)
{
    int m = 0, tmp = n;
    for (int i = 0; tmp > 0; i++)
    {
        arr[i] = tmp % 10;
        tmp /= 10;
        m++;
    }
    for (int j = 0; j < m; j++)
    {
        brr[j] = 1;
    }
    for (int i = 0; i < m; i++)
    {
        for (int j = 0; j < m; j++)
        {
            for (int k = 0; k < m; k++)
            {
                brr[j] = brr[j] * arr[k];
            }
        }
    }
    int sum = 0;
    for (int k = 0; k < m; k++)
    {
        sum += arr[k];
    }
    if (sum == n)
        cout << "True";
    else
        cout << "False";
}
int main()
{
    int n, arr[N], brr[N];
    cin >> n;
    Ams(arr, brr, n);
    return 0;
}