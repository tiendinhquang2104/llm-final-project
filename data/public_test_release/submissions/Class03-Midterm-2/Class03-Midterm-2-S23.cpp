#include <iostream>
using namespace std;
const int szMax = 10001;
void Input(long long a[], int &n)
{
    cin >> n;
    for (int i = 0; i < n; i++)
    {
        cin >> a[i];
    }
}
void Remove(long long a[], int &n, int idx)
{
    long long b[szMax];
    int np = 0;
    for (int i = 0; i < n; i++)
    {
        if (i == idx)
        {
            continue;
        }
        b[np] = a[i];
        np++;
    }
    for (int i = 0; i < np; i++)
    {
        a[i] = b[i];
    }
    n--;
}
void Process(long long a[], int &n)
{
    long long b[szMax];
    for (int i = 0; i < szMax; i++)
    {
        b[i] = 0;
    }
    for (int i = 0; i < n; i++)
    {
        b[a[i]]++;
    }
    for (int i = 0; i < szMax; i++)
    {
        while (b[i] > 1)
        {
            Remove(a, n, i);
            b[i]--;
        }
    }
}
void Output(long long a[], int n)
{
    cout << n << endl;
    for (int i = 0; i < n; i++)
    {
        cout << a[i] << " ";
    }
}
int main()
{
    int n;
    long long a[szMax];
    Input(a, n);
    Process(a, n);
    Output(a, n);
    return 0;
}