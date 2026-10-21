#include <iostream>
#include <cmath>
using namespace std;

bool isArmstrong(int num)
{
    int originalNum = num, sum = 0, digits = 0;
    while (originalNum != 0)
    {
        digits++;
        originalNum /= 10;
    }

    originalNum = num;
    while (originalNum != 0)
    {
        int digit = originalNum % 10;
        sum += pow(digit, digits);
        originalNum /= 10;
    }

    return sum == num;
}

int main()
{
    int num;
    cin >> num;

    if (isArmstrong(num))
    {
        cout << "True";
    }
    else
    {
        cout << "False";
    }

    return 0;
}
