#include <iostream>

using namespace std;
int n, a[10001], b[10001];
bool kt[10001];
int main()
{
    cin >> n;
    for (int i = 1; i <= n; i++)
    {
        cin >> a[i];
        kt[i] = true;
    }
    int sl = 0;
    for (int i = 1; i <= n; i++)
    {
        if (kt[i])
        {
            sl++;
            b[sl] = a[i];
            for (int j = i; j <= n; j++)
                if (a[i] == a[j])
                    kt[j] = false;
        }
    }
    cout << sl << endl;
    for (int i = 1; i <= sl; i++)
        cout << b[i] << " ";
}
