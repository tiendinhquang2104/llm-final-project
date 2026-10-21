#include <iostream>
using namespace std;

#define M 1000

bool Armstrong(int &a)
{
    int b = a;
    int mang[M];
    int n = 0;
    while (a != 0)
    {
        mang[n] = a % 10;
        n++;
        a = a / 10;
    }
    int sum = 0;
    int tich = 1;
    int j = 1;
    for (int i = 0; i < n; i++)
    {
        while (j < n)
        {
            tich *= mang[i];
            j++;
        }
        mang[i] = tich;
    }
    for (int i = 0; i < n; i++)
        sum += mang[i];
    if (sum == b)
        return true;
    return false;
}

int main()
{
    int a;
    cin >> a;
    if (Armstrong(a))
        cout << "True";
    else
        cout << "False";
    return 0;
}