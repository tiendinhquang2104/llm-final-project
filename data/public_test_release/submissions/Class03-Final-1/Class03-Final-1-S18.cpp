#include <iostream>
#include <string>
using namespace std;

int main()
{
    string first, last;
    cin >> first >> last;
    string t;
    bool kt = false;
    for (int i = 1; i <= (int)first.size(); i++)
    {
        for (int j = 1; j <= (int)last.size(); j++)
        {
            string candidate = first.substr(0, i) + last.substr(0, j);
            if (!kt || candidate < t)
            {
                t = candidate;
                kt = true;
            }
        }
    }
    cout << t << "\n";
    return 0;
}