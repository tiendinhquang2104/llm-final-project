#include <iostream>
#include <string>
#include <fstream>

using namespace std;

string Solve(string &s1, string &s2)
{
    string res = "";
    bool first = true;

    for (int i = 1; i <= s1.length(); i++)
    {
        string sub1 = s1.substr(0, i);
        for (int j = 1; j <= s2.length(); j++)
        {
            string sub2 = s2.substr(0, j);
            string cur = sub1 + sub2;

            if (first)
            {
                res = cur;
                first = false;
            }
            else if (cur < res)
            {
                res = cur;
            }
        }
    }

    return res;
}

int main()
{
    string s1, s2;

    cin >> s1 >> s2;

    cout << Solve(s1, s2);
    return 0;
}
