#include <iostream>
#include <string>
#include <cstring>

using namespace std;
int main()
{
    string first, last;
    cin >> first >> last;
    string ans = "";
    bool firstTime = true;
    for (int i = 1; i < first.length(); i++)
    {
        string preFirst = first.substr(0, i);
        for (int j = 1; j <= last.length(); j++)
        {
            string preLast = last.substr(0, j);
            string username = preFirst + preLast;
            if (firstTime || username < ans)
            {
                ans = username;
                firstTime = false;
            }
        }
    }
    cout << ans;
    return 0;
}