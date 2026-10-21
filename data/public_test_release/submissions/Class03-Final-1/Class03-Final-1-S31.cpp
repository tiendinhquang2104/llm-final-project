
#include <iostream>
#include <string>
using namespace std;

int main()
{
    string s, t;
    if (!(cin >> s >> t))
        return 0;
    string best;
    bool first = true;
    for (int i = 1; i <= (int)s.size(); ++i)
    {
        for (int j = 1; j <= (int)t.size(); ++j)
        {
            string u = s.substr(0, i) + t.substr(0, j);
            if (first || u < best)
            {
                best = u;
                first = false;
            }
        }
    }
    cout << best << '\n';
    return 0;
}
