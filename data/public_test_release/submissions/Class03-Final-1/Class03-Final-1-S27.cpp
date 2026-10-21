#include <iostream>
#include <string>

using namespace std;

int compare(string a, string b)
{
    int idx = 0;
    while (a[idx] == b[idx])
        ++idx;
    if (a.length() == b.length() && idx == a.length())
        return 2;
    return int(a[idx]) < int(b[idx]);
}

string getStr(string &s)
{
    int idx = 0;
    string res = "";
    while (idx < s.length() && s[idx] != ' ')
    {
        res += s[idx];
        ++idx;
    }
    s.erase(0, idx + 1);
    return res;
}

int main()
{
    string res = "";
    string s;
    getline(cin, s);
    string ten = getStr(s);
    string ho = getStr(s);
    string prefixName = "";
    for (int i = 0; i < ten.length(); ++i)
    {
        prefixName += ten[i];
        string prefixLastName = "";
        for (int j = 0; j < ho.length(); ++j)
        {
            prefixLastName += ho[j];
            if (res == "")
            {
                res = prefixName + prefixLastName;
                continue;
            }
            int comp = compare(res, prefixName + prefixLastName);
            if (comp == 0)
                res = prefixName + prefixLastName;
        }
    }
    cout << res;
    return 0;
}