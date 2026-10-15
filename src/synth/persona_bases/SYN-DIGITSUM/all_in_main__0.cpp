#include <iostream>
#include <string>
using namespace std;

int main()
{
    string s;
    cin >> s;
    int sum = 0;
    for (int i = 0; i < (int)s.size(); i++)
    {
        sum = sum + (s[i] - '0');
    }
    cout << sum << endl;
    return 0;
}
