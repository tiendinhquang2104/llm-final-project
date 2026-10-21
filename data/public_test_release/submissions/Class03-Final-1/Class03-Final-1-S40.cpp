#include <iostream>
#include <string>
using namespace std;
int main()
{
    string fname, lname;
    cin >> fname >> lname;
    string mininame = fname + lname;
    int x = fname.length();
    int y = lname.length();
    for (int i = 1; i <= x; i++)
    {
        for (int j = 1; j <= y; j++)
        {
            string user = fname.substr(0, i) + lname.substr(0, j);
            if (user < mininame)
            {
                mininame = user;
            }
        }
    }
    cout << mininame << endl;
    return 0;
}