#include <iostream>
#include <string>

using namespace std;

int main()
{
    string str;
    char temp = 'a';
    getline(cin, str);
    int n = str.length();
    for (int i = 0; i < n; i++)
    {
        if (str[i] == ' ')
        {
            temp = str[i + 1];
        }
    }
    cout << str[0];
    for (int i = 1; i < n; i++)
    {

        if (str[i] <= temp)
        {
            if (str[i] != ' ')
            {
                cout << str[i];
            }

            if (str[i] == ' ')
            {
                break;
            }
        }
    }
    cout << temp;
    return 0;
}