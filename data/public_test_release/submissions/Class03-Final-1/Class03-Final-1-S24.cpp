#include <iostream>
#include <string>
using namespace std;
void Input(string &name)
{
    getline(cin, name);
}

int Compare(string s1, string s2)
{
    int nS1 = s1.length();
    int nS2 = s2.length();
    int i = 0, j = 0;
    while (i < nS1 && j < nS2)
    {
        if (s1[i] == s2[j])
        {
            i++;
            j++;
        }
        if (s1[i] < s2[j])
        {
            return 1;
        }
        if (s1[i] > s2[j])
        {
            return 2;
        }
    }
    if (i < nS1)
    {
        return 1;
    }
    if (j < nS2)
    {
        return 2;
    }
    return 0;
}

void Process(string name)
{
    int n = name.length();
    string tmp[100];
    int np = 0;
    string ch;
    for (int i = 0; i < n + 1; i++)
    {
        if (name[i] == ' ' || i == n)
        {
            tmp[np] = ch;
            np++;
            ch.clear();
            continue;
        }
        ch += name[i];
    }
    string ans;
    string kq[100];
    int k = 0;
    for (int i = 0; i < np; i++)
    {
        string check;
        ans.clear();
        for (int j = 0; j < tmp[i].length(); j++)
        {
            check += tmp[i][j];
            if (ans.empty() || Compare(ans, check) == 2)
            {
                ans = check;
            }
        }
        check.clear();
        kq[k] = ans;
        k++;
    }
    for (int i = 0; i < k; i++)
    {
        cout << kq[i];
    }
}
int main()
{
    string name;
    Input(name);
    Process(name);
    return 0;
}