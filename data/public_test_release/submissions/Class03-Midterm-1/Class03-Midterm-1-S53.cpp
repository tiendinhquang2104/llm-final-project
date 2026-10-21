#include <iostream>
using namespace std;
int demso(int n)
{
    int count = 0, i = 0;
    while (n > 0)
    {
        count++;
        n = n / 10;
    }
    return count;
}
void arms(int n)
{
    double Sum = 0;
    int digit;
    while (n > 0)
    {
        digit = n % 10;
        for (int i = 1; i <= demso(n); i++)
        {
            digit *= digit;
            Sum += digit;
        }
        n = n / 10;
    }
    if (n == Sum)
    {
        cout << "True";
    }
    else
    {
        cout << "False";
    }
}
int main()
{
    int n;
    cin >> n;
    arms(n);
    return 0;
}