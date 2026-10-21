#include <iostream>
#include <string>
using namespace std;

int main()
{

    string a1, a2;
    cin >> a1 >> a2;
    int numL = a1.length();
    a1 = " " + a1;
    char pi = a2[0];
    int tmp = pi - 'a';
    string res = "";
    res += a1[1];
    for (int i = 2; i < numL; i++)
    {
        int currL = a1[i] - 'a';
        if (currL >= tmp)
            break;
        res = res + a1[i];
    }
    res += pi;
    cout << res;
    return 0;
}
