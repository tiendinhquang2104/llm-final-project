#include <iostream>
#include <string>

using namespace std;

int main()
{
    string s;
    getline(cin, s);
    int lc = 0;
    for (int i = 0; i < s.length(); i++)
    {
        if (s[i] == ' ')
        {
            lc = i + 1;
            break;
        }
    }
    string res;
    bool fin = false;
    int idx = 0;
    while (fin == false)
    {
        if (s[idx] <= s[lc] || idx == 0)
        {
            res.push_back(s[idx]);
        }
        else
        {
            res.push_back(s[lc]);
            fin = true;
        }
        idx++;
        if (idx == lc - 1)
        {
            res.push_back(s[lc]);
            break;
        }
    }
    cout << res;
    return 0;
}