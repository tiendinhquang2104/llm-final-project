#include <iostream>
#include <string>
#include <cctype>
using namespace std;
int main()
{
    string s;
    string res = "";
    while (getline(cin, s))
    {
        for (int i = 0; i < s.length(); i++)
        {
            string password = "";
            if (s[i] == ' ')
                continue;
            if (s[i] != ' ' && password.length() <= 10)
            {
                password += s[i];
            }
            else
            {
                if (password.length() > 0)
                {
                    password += s[i];
                }
            }
            res += password;
        }
    }
    cout << res;
    return 0;
}