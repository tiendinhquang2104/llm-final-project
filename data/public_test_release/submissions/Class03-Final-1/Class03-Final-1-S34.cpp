#include <iostream>
#include <string>

using namespace std;
string s, ans, cur, s1, s2;
main()
{
    ans = "zzzzzzzzzz";
    getline(cin, s);
    int pos = 0;
    while (s[pos] != ' ')
        pos++;
    for (int i = 0; i < pos; i++)
    {
        s1 += s[i] ;
        s2 = "" ;
        for (int j = pos + 1; j < s.size(); j++)
        {
            s2 += s[j];
            //cout << s1 << " " << s2 << '\n';
            cur = s1 + s2;
            if (ans > cur)
                ans = cur;
        }
    }
   // cout << s1 << " " << s2 << '\n' ;
    cout << ans << '\n';
}
