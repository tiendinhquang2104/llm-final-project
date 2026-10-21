#include <iostream>
#include <string>
using namespace std;

int main()
{
    string s1, s2;
    cin >> s1 >> s2;
    string res;
    int n = s1.length();
    int m = s2.length();
    int i, j;
    i = j = 0;
    res = s1.substr(0, 1);
    for (int i = 1; i < n; i++)
    {
        if (s1[i] < s2[0])
        {
            res = res + s1[i];
        }
        else
        {
            break;
        }
    }
    res += s2[0];
    cout << res;
    return 0;
}