#include <iostream>

unsigned int n;
bool res;

void input()
{
    std::cin >> n;
}

void output()
{
    if (res)
        std::cout << "True";
    else
        std::cout << "False";
}

int myPower(int n, int d)
{
    int res = n;
    for (int i = 2; i <= d; i++)
    {
        res *= n;
    }

    return res;
}

int countDigit(unsigned int n)
{
    int res = 0;
    while (n != 0)
    {
        n /= 10;
        res++;
    }
    return res;
}

bool check(unsigned int n)
{
    int digits = countDigit(n);
    unsigned int tempSum = 0, tempN = n;
    while (tempN != 0)
    {
        int recentDigit = tempN % 10;
        tempSum += myPower(recentDigit, digits);
        tempN /= 10;
    }

    if (tempSum == n)
        return true;
    return false;
}

int main()
{
    input();
    res = check(n);
    output();

    return 0;
}