#include <iostream>
#include <string>

using namespace std;

int main()
{
    string first, last;
    cin >> first >> last;

    string res;
    bool init = false;
    for (int i = 1; i <= first.size(); i++)
    {
        for (int j = 1; j <= last.size(); j++)
        {
            string cur = first.substr(0, i) + last.substr(0, j);
            if (!init || cur < res)
            {
                res = cur;
                init = true;
            }
        }
    }
    cout << res;
    return 0;
}
