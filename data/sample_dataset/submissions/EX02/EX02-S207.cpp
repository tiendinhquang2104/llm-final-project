#include <iostream>
using namespace std;
int luythua(int n, int count)
{
    int y = n;
    for (int i = 1; i < count; i++)
    {
        int x = n;
        int y = y * x;
    }
    return y;
}
int main()
{
    int n;
    cin >> n;
    int tmp = n;
    int tmp1 = n;
    int tmp2 = n;
    int count = 0;
    int sum = 0;
    int x;
    while (tmp2 != 0)
    {
        count += 1;
        tmp2 = tmp2 / 10;
    }
    for (int i = 1; i <= count; i++)
    {
        int x = tmp % 10;
        tmp = tmp / 10;
        sum += luythua(x, count);
    }
    if (sum == tmp1)
    {
        cout << "True";
    }
    else
    {

        cout << "False";
    }
    return 0;
}