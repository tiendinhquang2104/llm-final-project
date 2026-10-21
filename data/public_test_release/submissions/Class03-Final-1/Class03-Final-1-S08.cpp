#include <iostream>
#include <string>
using namespace std;
int main()
{
    string s;
    getline(cin, s);
    string n;
    getline(cin, n);
    string a;
    string b;

    for (int i = 0; i < s.length(); i++)
    {
        if (s[0] != ' ')
        {
            a = s[0];
        }
    }
    for (int i = 0; i < n.length(); i++)
    {
        if (n[i] != ' ')
        {
            b = n[i];
        }
    }
    if (a == b)
    {
        cout << "False" << endl;
    }
    cout << a + b << endl;
    return 0;
}