#include <iostream>
#include <cstring>
using namespace std;

int main()
{
    char s[1005];
    cin >> s;
    int d = 0;
    for (int i = 0; i < (int)strlen(s); i++)
        if (s[i] >= 65 && s[i] <= 90)
            d++;
    cout << d;
    return 0;
}
