#include <iostream>
using namespace std;
void inputArray(int a[], int n)
{
    for (int i = 0; i < n; i++)
    {
        cin >> a[i];
    }
}
void remove(int a[], int n)
{
    int count = 0;
    for (int i = 0; i < n - 1; i++)
    {
        if (a[i] = a[i + 1])
            cout << " ";
        else
        {
            cout << a[i];
            count++;
        }
        for (int i = 0; i < count; i++)
        {
            cout << a[i] << " ";
        }
        cout << count;
    }
}
int main()
{
    int n, a[100];
    cin >> n;
    inputArray(a, n);
    remove(a, n);
}
