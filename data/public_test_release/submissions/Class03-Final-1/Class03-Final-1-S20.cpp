#include <iostream>
#include <fstream>
#include <string>

using namespace std;

void Input(string &s)
{
    cout << "Nhap ho ten (ten truoc, ho sau): \n";
    getline(cin, s);

    for (int i = 0; i < s.length(); i++)
        s[i] = tolower(s[i]);
}

string getWord(string s, int n, int &idx)
{
    while (s[idx] == ' ')
        idx++;
    string word = "";
    while (idx < n && s[idx] != ' ' && s[idx] >= 'a' && s[idx] <= 'z')
    {
        word += s[idx];
        idx++;
    }
    return word;
}

string genUsername(string fullname)
{
    int length = fullname.length();
    string name[2];
    int k = 0;
    for (int i = 0; i < length; i++)
    {
        name[k] = getWord(fullname, length, i);
        k++;
    }

    string user = "";
    user += name[0][0];
    int i = 0;
    int j = 0;
    int ten = name[0].length();
    int ho = name[1].length();

    if (name[0][0] < name[0][1])
    {
        while (name[0][i] < name[0][i + 1] && i < ten - 1)
        {
            user += name[0][i + 1];
            i++;
        }
        if (name[1][0] < name[1][1])
            user += name[1][0];
    }
    else if (name[0][0] > name[0][1])
    {
        while (name[0][i] > name[0][i + 1] && i < ten - 1)
        {
            user += name[0][i + 1];
            i++;
        }
        if (name[1][0] > name[1][1])
            user += name[1][0];
    }
    return user;
}

int main()
{
    string name = "";
    Input(name);
    string username = genUsername(name);
    if (username.length() < 1)
        cout << "Ten dang nhap qua ngan.\n";
    else if (username.length() > 10)
    {
        for (int i = 0; i < 10; i++)
            cout << username[i];
    }
    else if (username.length() >= 1 && username.length() <= 10)
        cout << username;
    return 0;
}
