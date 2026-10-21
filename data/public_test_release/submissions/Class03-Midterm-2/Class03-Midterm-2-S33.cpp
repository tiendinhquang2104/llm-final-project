#include <iostream>
using namespace std;
const int N = 1e6 + 5;
int n, a[N], cnt = 1, res[N];
 bool check = true;
int main()
{
    cin >> n;
    for (int i = 1; i <= n; i++)
    {
        cin >> a[i];
    }

    for (int i = 1; i <= n; i++)
    {
        for (int j = 1; j < i; j++)
        {
            if (a[j] == a[i])
                check = false;
        }
        if (check == true)
        {
            res[cnt] = a[i];
            cnt++;
        }
        check = true;
    }
    cout << cnt - 1 << '\n';
    for (int i = 1; i <= cnt - 1; i++)
        cout << res[i] << " ";
}
