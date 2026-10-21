#include <iostream>

using namespace std;
bool armstrong(int n)
{
    int sum = 0, ans = n;
    int count = 0, temp = n;
    while (n != 0)
    {
        int temp = n % 10;
        count++;
        n /= 10;
    }

    n = temp;
    while (n != 0)
    {
        int res = 1;
        int temp = n % 10;
        for (int i = 1; i <= count; i++)
        {
            res *= temp;
        }
        sum += res;
        n /= 10;
    }

    if (sum == ans)
    {
        return true;
    }
    else
    {
        return false;
    }
}
int main()
{
    int n;
    cin >> n;
    if (armstrong(n))
    {
        cout << "True" << endl;
    }
    else
    {
        cout << "False" << endl;
    }
}