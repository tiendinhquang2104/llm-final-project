#include <iostream>
using namespace std;

int main()
{
    int n, g, x;
    cin >> n >> g;
    for (int i = 1; i < n; i++)
    {
        cin >> x;
        while (x != 0)
        {
            int r = g % x;
            g = x;
            x = r;
        }
    }
    cout << g;
    return 0;
}
