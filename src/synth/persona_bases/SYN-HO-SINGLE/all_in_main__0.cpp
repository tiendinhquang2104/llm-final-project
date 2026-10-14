#include <iostream>
#include <string>
using namespace std;

int main()
{
    string s;
    cin >> s;
    int sum = 0;
    for (int i = 0; i < (int)s.size(); i++)
        sum += s[i] - '0';
    cout << (sum % 3 == 0 ? "True" : "False");
    return 0;
}
