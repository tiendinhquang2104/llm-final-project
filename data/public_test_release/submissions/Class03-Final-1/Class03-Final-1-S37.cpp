#include <iostream>

using namespace std;

string theBest(string firstName, string lastName)
{
    string best = "";
    bool firstSet = false;

    for (int i = 1; i <= (int)firstName.size(); i++)
    {
        for (int j = 1; j <= (int)lastName.size(); j++)
        {
            string candidate = firstName.substr(0, i) + lastName.substr(0, j);
            if (!firstSet || candidate < best)
            {
                best = candidate;
                firstSet = true;
            }
        }
    }

    return best;
}

int main()
{
    string firstName, lastName;
    cin >> firstName >> lastName;

    cout << theBest(firstName, lastName) << endl;

    return 0;
}