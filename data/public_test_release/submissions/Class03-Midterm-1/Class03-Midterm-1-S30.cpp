#include <iostream>

using namespace std;

int power(int &a, int &b)
{
    int power = a;
    for (int i = 0; i < b - 1; i++)
    {
        power *= a;
    }
    return power;
}

int main()
{

    int m;
    int n;
    int a[50];
    cin >> n;
    m = n;
    bool flag = false;

    int j = 0;

    do
    {
        a[j] = m % 10;
        m /= 10;
        j++;
    } while (m % 10 != 0);

    for (int i = 1; i < 50; i++)
    {
        int sum = 0;
        for (int k = 0; k < j; k++)
        {
            sum += power(a[k], i);
        }
        if (sum == n)
        {
            cout << "True" << endl;
            flag = true;
        }
    }
    if (flag == false)
    {
        cout << "False" << endl;
    }

    // for (int i = 0; i < j; i++)
    // {
    //     cout << a[i] << " " << endl;
    // }
}