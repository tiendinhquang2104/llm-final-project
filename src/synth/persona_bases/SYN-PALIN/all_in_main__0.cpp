#include <iostream>
#include <string>
using namespace std;

int main()
{
    string s;
    cin >> s;
    int n = s.length();
    bool ok = true;
    for (int i = 0; i < n / 2; i++)
    {
        if (s[i] != s[n - 1 - i])
        {
            ok = false;
            break;
        }
    }
    if (ok)
        cout << "True";
    else
        cout << "False";
    return 0;
}
