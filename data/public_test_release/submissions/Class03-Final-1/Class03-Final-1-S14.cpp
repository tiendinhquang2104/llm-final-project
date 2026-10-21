#include <iostream>
#include <string>
#include <fstream>
using namespace std;
int main()
{
    string s;
    getline(cin, s);
    string words[2];
    int i = 0;
    int n = 0;
    while (i < s.size())
    {
        while (i < s.size() && s[i] == ' ')
            i++;
        if (i >= s.size())
            break;
        string w;
        while (i < s.size() && s[i] != ' ')
        {
            w.push_back(s[i++]);
        }
        words[n++] = w;
    }
    string ans;
    ans.push_back(words[0][0]);

    for (int i = 1; i <= words[0].size(); i++)
    {
        if (words[0][i] < words[1][0])
        {
            ans.push_back(words[0][i]);
        }
    }
    ans.push_back(words[1][0]);
    cout << ans;
    return 0;
}