#include <iostream>
#include <string>
using namespace std;
int main()
{
    string line;

    cin >> line;
    int u = line.size();
    int x = 0;
    int p1 = 0;
    while (x < u)
    {
        if (line[x] == ' ')
        {
            p1 = x;
            break;
        }
        x++;
    }
    string ho = line.substr(0, p1);
    string ten = line.substr(p1 + 1, u - 1 - p1 - 1 + 1);

    int daiho = ho.size();
    int daiten = ten.size();
    char c = ten[0];
    int i = 0;
    int end;
    while (i < daiho)
    {
        if (ho[i] > c)
        {
            end = i - 1;
            break;
        }
        i++;
    }
    for (int i = 0; i <= end; i++)
    {
        cout << ho[i];
    }
    cout << ten[0];

    return 0;
}