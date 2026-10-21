#include <iostream>
#include <string>
using namespace std;
int main()
{
    string s;
    getline(cin, s);
    int n = 0;

    for (int i = 0; i < (int)s.size(); i++)
    {
        if (s[i] == ' ')
        {
            n = i;
            break;
        }
    }
    string res, tmp;
    res = s[0] + s[n + 1];
    for (int i = 0; i < n; i++)
    {
        string temp;
        tmp = tmp + s[i];
        for (int j = n + 1; j < (int)s.size(); j++)
        {
            temp = temp + s[j];
            if (res > temp + tmp)
            {
                res = temp + tmp;
            }
        }
    }
    cout << res << endl;
    return 0;
}