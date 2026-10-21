#include <iostream>
using namespace std;
const int N = 10000;

void inputArr(int arr[N], int &n);
void outputArr(int arr[N], int n);
void DeleteDuplicates(int arr[N], int &n);

int main()
{
    int arr[N], n;
    inputArr(arr, n);
    DeleteDuplicates(arr, n);
    outputArr(arr, n);
    return 0;
}

void inputArr(int arr[N], int &n)
{
    cin >> n;
    for (int i = 0; i < n; i++)
    {
        cin >> arr[i];
    }
}
void outputArr(int arr[N], int n)
{
    cout << n << endl;
    for (int i = 0; i < n; i++)
    {
        cout << arr[i] << ' ';
    }
}
void DeleteDuplicates(int arr[N], int &n)
{
    int length = 1;
    int *newArr = new int[N];
    bool isContinue = true;
    for (int i = 0; i < n; i++)
    {
        if (i == 0)
        {
            newArr[i] = arr[i];
            continue;
        }
        for (int j = 0; j < i; j++)
        {
            if (arr[j] == arr[i])
            {
                isContinue = false;
                break;
            }
            isContinue = true;
        }
        if (isContinue)
        {
            newArr[length] = arr[i];
            length++;
        }
    }
    for (int i = 0; i < length; i++)
    {
        arr[i] = newArr[i];
    }
    delete[] newArr;
    n = length;
}
