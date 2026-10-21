#include <iostream>
#include <string>
#include <cctype>

using namespace std;

char toLowercase(char c)
{
    return tolower(c);
}

string createAbbreviation(const string &fullName)
{
    string abbreviation = "";
    bool newWord = true;
    for (int i = 0; i < fullName.length(); i++)
    {
        if (isalpha(fullName[i]))
        {
            if (newWord)
            {
                abbreviation += toLowercase(fullName[i]);
                newWord = false;
            }
        }
        else
        {

            newWord = true;
        }
    }

    return abbreviation;
}

int main()
{
    string fullName;

    getline(cin, fullName);

    string result = createAbbreviation(fullName);

    cout << result << endl;

    return 0;
}
