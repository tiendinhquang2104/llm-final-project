#include <iostream>
#include <fstream>
#include <string>
using namespace std;
string getToken(string s)
{
    int idx = 0;
    string token = "";
    while (s[idx] != '\0')
    {
        idx++;
    }
    while (s[idx] == '\0' && s[idx] >= 'a' && s[idx] <= 'z')
    {
        token += s[idx];
        idx++;
    }
    return token;
}
string getWord(string s)
{
    int length = s.size();
    string name[2];
    int k = 0;
    for (int i = 0; i < length; i++)
    {
        name[k] = getToken(s);
        k++;
    }
    string username = "";
    username += name[0][0];
    int i = 0, j = 0, l = 0;
    int ten = name[0].size(), ho = name[1].size();
    if (name[0][0] < name[0][1])
    {
        while (name[0][i] < name[0][i + 1] && i < ten - 1)
        {
            username += name[0][i];
            i++;
        }
        while (name[1][i] < name[1][i + 1] && i < ho - 1)
        {
            username += name[1][i];
            i++;
        }
    }
    else if (name[0][0] > name[0][1])
    {
        while (name[0][i] > name[0][i + 1] && i < ten - 1)
        {
            username += name[0][i];
            i++;
        }
        if (name[1][0] > name[1][1])
            username += name[1][0];
    }
    cout << username << endl;
    return username;
}
int main()
{
    string s;
    cout << "Nhap ho ten (ten truoc, ho sau) " << "\n";
    getline(cin, s);
    getToken(s);
    getWord(s);
}