#include <iostream>
using namespace std;

int main()
{
    int n, x, mx;
    cin >> n;
    cin >> mx;
    for (int i = 1; i < n; i++)
    {
        cin >> x;
        if (x > mx)
            mx = x;
    }
    cout << mx;
    return 0;
}
