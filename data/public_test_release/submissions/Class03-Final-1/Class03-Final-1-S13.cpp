#include <iostream>
#include <string>
using namespace std;

int main()
{
    string ans[2];
    string s;
    getline(cin, s);
    s = s + ' ';
    int cnt = 0;
    for (int i = 0; i < s.size(); i++)
    {
        if (s[i] == ' ')
        {
            cnt++;
            continue;
        }
        if (cnt > 1)
            break;
        ans[cnt] += s[i];
    }

    int i = 1;
    string final = "";
    final += ans[0][0];

    while (i < ans[0].length())
    {
        if (ans[0][i] >= ans[1][0])
        {
            cout << final + ans[1][0] << '\n';
            exit(0);
        }

        final += ans[0][i];
        i++;
    }

    cout << final + ans[1][0] << '\n';
}