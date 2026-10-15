#include <iostream>
#include <cstring>
using namespace std;

int main()
{
    char s[1005];
    cin >> s;
    int n = strlen(s);
    for (int i = 0; i < n; i++)
    {
        if (s[i] >= 'a' && s[i] <= 'z')
            s[i] = s[i] - 32;
    }
    cout << s;
    return 0;
}
