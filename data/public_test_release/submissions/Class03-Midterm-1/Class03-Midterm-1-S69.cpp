#include <iostream>

using namespace std;

bool isArmStrongNumber(int n)
{
    int cnt = 0;
    int sum = 0;
    int val = n;
    int index = 0;
    while (n > 0)
    {
        n /= 10;
        cnt++;
    }
    n = val;
    for (int i = 0; i < cnt; i++)
    {
        index = val % 10;
        for (int i = 1; i < cnt; i++)
        {
            index *= val % 10;
        }
        sum += index;
        val /= 10;
    }
    if (sum == n)
        return true;
    else
        return false;
}

int main()
{
    int n;
    cin >> n;
    switch (isArmStrongNumber(n))
    {
    case 0:
        cout << "False";
        break;
    case 1:
        cout << "True";
        break;
    }
    return 0;
}