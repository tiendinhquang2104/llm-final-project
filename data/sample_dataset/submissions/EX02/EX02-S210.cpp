#include <iostream>

using namespace std;
int a(long n)
{
    int b = 0;
    while (n != 0)
    {
        b++;
        n /= 10;
    }
}
int main()
{
    int n, m;
    cin >> n;
    m = n;
    int b = a(n);
    long sum = 0;
    while (n != 0)
    {
        int d = n % 10;
        }
    if (sum == n)
        cout << "True";
    else
        cout << "False";
    return 0;
}