#include <iostream>
#include <string>
using namespace std;

int main()
{
    string first, last;
    cout << "Nhap ho va ten: ";
    cin >> first >> last;
    string best = "";
    best += first[0];
    for (int i = 1; i <= first.length(); i++)
    {
        string preFirst = first.substr(0, i);
        for (int j = 0; j <= last.length(); j++)
        {
            string preLast = last.substr(0, j);
            string candidate = preFirst + preLast;
            if (best == "" || candidate < best)
            {
                best = candidate;
            }
        }
    }

    cout << best;
    return 0;
}