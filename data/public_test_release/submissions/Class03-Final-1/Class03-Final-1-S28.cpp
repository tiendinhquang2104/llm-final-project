#include <iostream>
#include <string>

using namespace std;
bool cmp(string u, string v)
{
    int MIN = v.length();
    if (u.length() < v.length()) MIN = u.length();
    for (int i = 0; i < MIN; i++)
    if (u[i] != v[i])
    {
        if (u[i] > v[i]) return true;
        else return false;
    }
    if (u.length() > v.length()) return true;
    return false;
}
int main()
{
    string u, v;
    string a[1001];
    int len = 0;

    cin >> u >> v;

    string tmpu = "";

    for (int i = 0; i < u.length(); i++ )
    {
        tmpu += u[i];
        string tmpv = "";
        for (int j = 0; j < v.length(); j++)
        {
            tmpv += v[j];
            a[len] = tmpu + tmpv;
            len++;
        }
    }
    string ans = a[0];
    for (int i = 1; i < len; i++)
    {
        if (cmp(ans, a[i]) == 1)
        {
            ans = a[i];
        }
    }
    cout << ans;
    return 0;
}
