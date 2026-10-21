#include <iostream>
#define MAX 100
using namespace std;
long long RemoveDuplicatesFromArray(int arr[], int n)
{
    int temp[MAX];
    int j = 0;
    for (int i = 0; i < n - 1; i++)
    {
        if (arr[i] != arr[i + 1])
        {
            temp[j++] = arr[i];
        }
    }
    temp[j++] = arr[n - 1];
    for (int i = 0; i < j; i++)
    {
        arr[i] = temp[i];
    }
    return j;
}
int main()
{
    int n;
    cin >> n;
    int arr[MAX];
    for (int i = 0; i < n; i++)
    {
        cin >> arr[i];
    }
    n = RemoveDuplicatesFromArray(arr, n);
    cout << n << endl;
    for (int i = 0; i < n; i++)
    {
        cout << arr[i] << " ";
    }
    return 0;
}