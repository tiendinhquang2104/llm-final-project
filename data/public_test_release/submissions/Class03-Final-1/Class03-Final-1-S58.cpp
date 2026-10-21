#include <iostream>
#include <string>
#include <cstring>
#include <fstream>
using namespace std;
int main()
{
    string s1, s2;
    cin >> s1 >> s2;
    int t1 = 0;
    for (int i = 1; i < s1.length(); i++)
    {
        if (s1[i] > s2[0])
        {
            break;
        }
        t1 = i;
    }
    for (int i = 0; i <= t1; i++)
    {
        cout << s1[i];
    }
    cout << s2[0];
}