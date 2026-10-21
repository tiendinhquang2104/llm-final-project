#include <iostream>
#include <string>
using namespace std;
int main()
{
    string x;
    getline(cin, x);
    int j = 0;
    for (int i = 0; i < x.size(); i++)
    {
        if (x[i] == ' ')
        {
            j = i;
            break;
        }
    }
    string mi, tmp;
    mi = x[0] + x[j + 1];
    for (int i = 0; i < j; i++)
    {
        string tam;
        tmp = tmp + x[i];
        for (int ii = j + 1; ii < x.size(); ii++)
        {
            tam = tam + x[ii];
            if (mi > tmp + tam)
                mi = tmp + tam;
        }
    }
    cout << mi;
    return 0;
}