#include <iostream>
using namespace std;

long long mu(long long n, int k)
{
    if(k == 0) return 1;
    long long temp = mu(n,k/2);
    return k % 2 == 0 ? temp * temp : temp * temp * n;
}

int sl(long long n)
{
    int cnt = 0;
    while(n > 0)
    {
        n/=10;
        cnt++;
    }
    return cnt;
}

bool checkArmstrong(long long n, int d)
{
    long long temp = 0;
    long long temp_n = n;
    while(temp_n > 0)
    {
        long long cur = temp_n % 10;
        temp_n /= 10;
        temp += mu(cur,d);
    }
    if(temp == n)
        return true;
    return false;
}

int main()
{
    long long n;
    cin >> n;
    if(checkArmstrong(n,sl(n)))
        cout << "True";
    else cout << "False";
}