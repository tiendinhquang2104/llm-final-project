#include <iostream>
#include <string>

using namespace std;

string tiento(string s1, string s2)
{
    string ans = "zzzzzzzzzz";
    int sizeS1 = s1.length();
    int sizeS2 = s2.length();
    for (int i = 1; i <= sizeS1; i++) // do dai tien to s1
    {
        string tmp = "";
        string sub1 = s1.substr(0, i);
        for (int j = 1; j <= sizeS2; j++) // do dai tien to s2
        {
            string sub2 = s2.substr(0, j);
            tmp = sub1 + sub2;
            if (ans > tmp)
                ans = tmp;
        }
    }
    return ans;
}

int main()
{
    string s1, s2;
    cin >> s1 >> s2;
    string ans = tiento(s1, s2);
    cout << ans;
    return 0;
}