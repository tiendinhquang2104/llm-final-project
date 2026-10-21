#include <iostream>
#include <string>
#define N 10000

using namespace std;

string str[N];
string tmp_1, tmp_2;

void make_name(string finame, string laname, int &cnt)
{
    cnt = 0;
    for (int i = 0; i < finame.size(); ++i)
    {
        tmp_1 = tmp_2;
        tmp_1 += finame[i];
        tmp_2 = tmp_1;
        for (int j = 0; j < laname.size(); ++j)
        {
            tmp_1 += laname[j];
            str[cnt] = tmp_1;
            ++cnt;
        }
    }
}
void SORT(string str[], int n)
{
    for (int i = 0; i < n; ++i)
        for (int j = i + 1; j < n; ++j)
            if (str[i] > str[j])
            {
                string tmp = str[i];
                str[i] = str[j];
                str[j] = tmp;
            }
}

int main()
{
    string finame, laname;
    int cnt;
    cin >> finame >> laname;
    make_name(finame, laname, cnt);
    SORT(str, cnt);
    cout << str[0];
    return 0;
}
