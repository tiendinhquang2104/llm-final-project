#include <iostream>
using namespace std;

bool checkBefore(int arr[], int stopIdx, int checkElement)
{
    for (int i = 0; i <= stopIdx; i++)
    {
        if (arr[i] == checkElement)
        {
            return false;
        }
    }
    return true; // OK to add
}
int main()
{
    int n;
    cin >> n;
    int arr[10001];
    int resArr[10001];
    for (int i = 0; i < n; i++)
    {
        cin >> arr[i];
    }

    int idx = 0;
    resArr[0] = arr[0];
    for (int i = 0; i < n; i++)
    {
        if (checkBefore(resArr, idx, arr[i]))
        {
            idx++;
            resArr[idx] = arr[i];
        }
    }
    cout << idx + 1 << endl;
    for (int i = 0; i <= idx; i++)
    {
        cout << resArr[i] << " ";
    }
}