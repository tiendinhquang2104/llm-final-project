#include <iostream>
#include <string>

using namespace std;

int main()
{
    string t,h;
    cin >> t >> h;
    int i = 1, j = 0;
    string ans;
    ans += t[0];
    while (i == 0 || j == 0)
    {
        if(i < t.size() && t[i] < h[j])
        {
            ans += t[i]; i++;
        }
        else if (j < h.size())
        {
            ans += h[j]; j++;
        }
    }
    cout << ans;
    return 0;
}
