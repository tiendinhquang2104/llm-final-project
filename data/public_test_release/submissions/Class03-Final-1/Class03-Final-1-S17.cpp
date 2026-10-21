#include <iostream>
#include <string>
#include <fstream>
#include <cstring>

using namespace std;

int main()
{
    string a, b;
    cin >> a >> b;
    string ans = "";
    ans += a[0];
    for (int i = 1; i < a.size(); i++)
    {
        // if (ans.size() >= 9)
        //     break;
        // khong ghi ro ten hay ten dang nhap
        if (ans + a[i] + b[0] < ans + b[0])
        {
            ans += a[i];
        }
        else
            break;
    }
    cout << ans + b[0];
    return 0;
}