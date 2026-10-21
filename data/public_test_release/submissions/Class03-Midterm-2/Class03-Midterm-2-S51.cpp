#include <iostream>
using namespace std;
void remove(int a[], int n)
{
    for (int i = 0; i < n; i++)
    {
        if (a[i] == a[i + 1])
        {
            a[i] = a[i + 1];
        }
        --a[i];
    }
    n--;
}
int main()
{
    int a[100];
    int n;
    cin >> n;
    for (int i = 0; i < n; i++)
    {
        cin >> a[i];
    }
    remove(a, n);
    cout << n << endl;
    for (int i = 0; i < n; i++)
    {
        cout << a[i] << " ";
    }
    return 0;
}