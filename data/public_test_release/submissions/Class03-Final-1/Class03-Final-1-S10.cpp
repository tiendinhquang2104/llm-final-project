#include <iostream>
#include <fstream>
#include <string>
#include <cstring>
using namespace std;

int main()
{
    string a;
    getline(cin, a);
    string b = "";
    string c = "";
    string tmp = "";
    for (int i = 1; i < a.length(); i++)
    {
        if (a[i - 1] == a[0] || a[i - 1] == ' ')
        {
            b += a[i];
        }
        if (a[i] != ' ')
        {
            tmp = b + a[i];
            if (b >= tmp)
            {
                b += a[i];
            }
        }
        if (a[i] == ' ')
        {
            tmp = "";
            c += b;
            b = "";
        }
    }
    cout << c << endl;
    return 0;
}