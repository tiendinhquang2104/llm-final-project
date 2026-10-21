#include<iostream>

using namespace std;

int n, cnt, a[100007], res[100007];

int main()
{
    cin >> n;
    cnt = 1;
    for(int i = 1; i <= n; i++) cin >> a[i];
    for(int i = 1; i <= n; i++)
    {
        bool ch = 1;
        for(int j = 1; j < i; j++)
        {
            if(a[i] == a[j])
            {
                ch = 0;
                break;
            }
        }
        if(ch)
        {
            res[cnt] = a[i];
            cnt++;
        }
    }
    cout << cnt-1 << endl;
    for(int i = 1; i < cnt; i++) cout << res[i] << " ";

    return 0;
}
