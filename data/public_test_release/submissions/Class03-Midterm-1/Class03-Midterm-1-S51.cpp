#include <iostream>
using namespace std;

bool checkArmstrongNum(int n);
long long int getPow(int n, int d);
int countDigit(int n);

int main()
{
    int n, sum = 0;
    cin >> n;
    cout << (checkArmstrongNum(n) ? "True" : "False");
    return 0;
}

long long int getPow(int n, int d)
{
    long long int result = 1;
    for (int i = 0; i < d; i++)
    {
        result *= n;
    }
    return result;
}
bool checkArmstrongNum(int n)
{
    int n_copy = n;
    long long int sum = 0;
    int d = countDigit(n);
    while (n > 0)
    {
        int digit = n % 10;
        sum += getPow(digit, d);
        n /= 10;
    }
    if (sum == n_copy)
        return true;
    else
        return false;
}
int countDigit(int n)
{
    int digits = 0;
    while (n > 0)
    {
        digits++;
        n /= 10;
    }
    return digits;
}