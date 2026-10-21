#include <iostream>
using namespace std;
int digt(int n)
{
    int count = 0;
    for (int i = n; i != 0; i = i / 10)
    {
        count++;
    }
    return count;
}
int main()
{
    int n;
    cin >> n;
    int s = 0;
    int a = digt(n);
    for (int k = n; k != 0; k = k / 10)
    {
        int b = k % 10;
        int sd = k % 10;
        for (int i = 0; i < a - 1; i++)
        {
            b = sd * b;
        }
        s = s + b;
    }
    if (s == n)
    {
        cout << "True";
    }
    else
    {
        cout << "False";
    }
}