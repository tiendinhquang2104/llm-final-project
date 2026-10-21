#include <iostream>
#include <string>

using namespace std;

int main()
{
    string a, b;
    cin >> a >> b;
    int i = 1;
    string ans = "";
    ans += a[0];
    while (a[i] < b[0])
    {
        ans += a[i];
        i++;
        if (i >= a.length())
            break;
    }
    ans += b[0];
    cout << ans;
    return 0;
}