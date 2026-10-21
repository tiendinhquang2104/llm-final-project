#include <iostream>

using namespace std;

long long a[100];
int main()
{
    long long n;
    cin >> n;
    long long tmp_n = n;
    int cnt = 0;
    while(tmp_n > 0)
    {
        a[cnt++] = tmp_n % 10;
        tmp_n /= 10;
    }
    long long sum = 0;
    for(int i = 0; i < cnt; i++)
    {
        long long tmp = 1;
        for(int j = 0; j < cnt; j++)
        {
            tmp *= a[i];
        }
        sum += tmp;
    }
    if(sum == n){cout << "True";}
    else {cout << "False";}
    return 0;
}
