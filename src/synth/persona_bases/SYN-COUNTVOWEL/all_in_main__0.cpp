#include <iostream>
#include <cstring>
using namespace std;

int main()
{
    char s[1005];
    cin >> s;
    int cnt = 0;
    for (int i = 0; s[i] != '\0'; i++)
    {
        switch (s[i])
        {
        case 'a':
        case 'e':
        case 'i':
        case 'o':
        case 'u':
            cnt++;
            break;
        }
    }
    cout << cnt;
    return 0;
}
