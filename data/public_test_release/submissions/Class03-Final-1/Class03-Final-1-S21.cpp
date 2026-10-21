#include <iostream>
#include <string>
#include <cstring>
using namespace std;
char a[256];
int main()
{
    ios::sync_with_stdio(false);
    cin.tie(nullptr);
    string s;
    getline(cin, s);
    for (int i = 0; i < s.size(); ++i)
    {
        a[i] = s[i];
    }
    string name = "";
    name += a[0];
    for (int i = 1; i < 256; ++i)
    {
        if (a[i] > a[i - 1])
            name += a[i - 1];
    }
    cout << name;
    return 0;
}
