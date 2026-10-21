#include <iostream>
#include <string>
using namespace std;

int main()
{
    string input;
    getline(cin, input);

    int place = input.find(' ');

    string firstname = input.substr(0, place);
    if (place == string::npos)
    {
        cout << firstname[0];
        return 1;
    }
    string lastname = input.substr(place + 1);
    string res = "";

    res += firstname[0];
    for (int i = 1; i < firstname.length(); i++)
    {
        if (firstname[i] < lastname[0])
        {
            res += firstname[i];
        }
    }

    res += lastname[0];
    cout << res << endl;
}