#include <iostream>
using namespace std;

const int MAX_N = 10000 + 10;

bool findValue(long long a[], int n, long long val)
{
    for(int i=0;i<n;i++)
        if(a[i] == val)
            return true;
    return false;
}

int main()
{
    int n;
    cin >> n;
    long long a[MAX_N],ans[MAX_N];
    int cnt = 0;
    for(int i=0;i<n;i++)
        cin >> a[i];
    for(int i=0;i<n;i++)
        if(!findValue(ans,cnt,a[i]))
            ans[cnt++] = a[i];
    cout << cnt << '\n';
    for(int i=0;i<cnt;i++)
        cout << ans[i] << ' ';
}