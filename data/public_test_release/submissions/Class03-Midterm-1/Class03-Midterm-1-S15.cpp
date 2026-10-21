#include <iostream>
using namespace std;
bool Ammstrong(int n);
bool Ammstrong(int n)
{
    int digits;
    long temp;
    temp = n;
    int d;
    if (n <= 1)
    {
        return false;
    }
    for (int i = 2; i < n; i++)
    {
        digits = temp % 10;
        temp = temp / 10;
    }
}

int main()
{
    int n;
    cin >> n;
    if (Ammstrong(n))
    {
        cout << "True";
    }
    else
    {
        cout << "False";
    }
    return 0;
}
