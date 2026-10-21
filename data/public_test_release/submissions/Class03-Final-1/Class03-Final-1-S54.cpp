#include <iostream>
#include <string>

using namespace std;

int main()
{
    string first, last;
    cin >> first >> last;
    string res;
    res = res + first[0];
    int n = first.length();
    for (int i = 1; i < n; i++)
    {
        if ((char)first[i] < (char)last[0])
            res = res + first[i];
        else
            break;
    }
    res += last[0];
    cout << res;
    return 0;
}