#include <iostream>
#include <fstream> 
#include <string>
#include <cstring>
using namespace std;

int main()
{
    string s1, s2;
    cin >> s1 >> s2;
    char maxx = s2[0];
    string ans = "";
    ans += s1[0];
    for(int i=1;i<s1.size();i++)
        if(s1[i] < maxx)
            ans += s1[i];
    ans += s2[0];
    cout << ans;
}