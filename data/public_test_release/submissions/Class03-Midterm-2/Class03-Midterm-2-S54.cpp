#include <iostream>

using namespace std;

// void removeFromArray(int a[], int &n, int k, int start) // xoa so k khoi mang, bat dau tu vi tri start + 1
// {
//     for (int i = start + 1; i < n; i++)
//     {
//         if (a[i] == k)
//         {
//             for (int j = i; i < n; j++)
//             {
//                 a[i] = a[i + 1];
//                 n--;
//                 i--;
//             }
//         }
//     }
// }
// void removeDuplicates(int a[], int &n)
// {
//     int startIndex = 0;
//     for (int i = startIndex; i < n; i++)
//     {
//         int k = a[i];
//         removeFromArray(a, n, k, i);
//     }
// }

void inputArray(int a[], int n)
{
    for (int i = 0; i < n; i++)
    {
        cin >> a[i];
    }
}

void outputArray(int a[], int n)
{
    for (int i = 0; i < n; i++)
    {
        cout << a[i] << " ";
    }
}

int main()
{
    int n, a[100];
    cin >> n;
    inputArray(a, n);
    for (int i = 0; i < n; i++)
    {
        int k = a[i];
        for (int j = i + 1; j < n; j++)
        {
            if (a[j] == k)
            {
                for (int v = j; j < n; v++)
                {
                    a[v] = a[v + 1];
                    n--;
                    j--;
                }
            }
        }
    }
    cout << n << endl;
    outputArray(a, n);
    return 0;
}