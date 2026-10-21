#include <iostream>
#include <string>

using namespace std;

int main()
{
    string s, st, a[1000], ten, ho;
    int cnt = 0;
    getline(cin, s);
    s += ' ';

    for (int i = 0; i < s.size(); i++)
    {
        if (s[i] != ' ')
            st += s[i];
        else if (st.size() > 0)
        {
            cnt++;
            a[cnt] = st;
            st = "";
        }
    }

    ten = a[1];
    ho = a[2];

    int d1 = 0, d2 = 0;
    string c[1000], d[1000];

    for (int j = 0; j < ten.size(); j++)
    {
        string tmp = ten.substr(0, j + 1);
        d1++;
        c[d1] = tmp;
    }

    for (int j = 0; j < ho.size(); j++)
    {
        string tmp = ho.substr(0, j + 1);
        d2++;
        d[d2] = tmp;
    }
    string Min = c[1] + d[1];
    for (int i = 1; i <= d1; i++)
    {
        for (int j = 1; j <= d2; j++)
        {
            string t = c[i] + d[j];
            if (t < Min)
            {
                Min = t;
            }
        }
    }
    cout << Min;

    return 0;
}