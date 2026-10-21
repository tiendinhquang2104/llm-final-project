#include <iostream>

using namespace std;

int main()
{
    string ho;
    string ten;
    string ds[100];
    int index = 0;
    cin >> ten >> ho;
    for (int i = 0; i < ten.length(); i++)
    {
        for (int j = 0; j < ho.length(); j++)
        {
            ds[index++] = ten.substr(0, i) + ho.substr(0, j);
        }
    }
    for (int i = 0; i < ten.length(); i++)
    {
        for (int j = i + 1; j < ho.length(); j++)
        {
            if (ds[j] <= ds[i])
            {
                string tmp = ds[i];
                ds[i] = ds[j];
                ds[j] = tmp;
            }
        }
    }
    cout << ds[0];
    return 0;
}