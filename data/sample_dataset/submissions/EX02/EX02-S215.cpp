#include<iostream>

using namespace std;

int n, t;

int dem(int n)
{
    int cnt = 0;
    while(n > 0)
    {
        n /= 10;
        cnt++;
    }
    return cnt;
}

int mu(int a, int b)
{
    if(b == 0) return 1;
    if(b == 1) return a;
    if(a == 1) return 1;
    t = mu(a,b/2);
    if(b%2==0) return t*t;
    else return t*a*t;
}

bool check()
{
    int x = n, sum = 0;
    while(x > 0)
    {
        int tem = x % 10;
        sum += mu(tem,t);
        x /= 10;
    }
    return (sum == n);

}

int main()
{
    cin >> n;
    t = dem(n);
    if(check()) cout << "True";
    else cout << "False";
}
