#include <iostream>
#include <string>

using namespace std;

string toLower(string& n) {
    int i = 0;
    while (i < n.length()) {
        n[i] -= 32;
        i++;
    }
    return n;
}

int main() {
    string firstName;
    string lastName;
    toLower(firstName);
    toLower(lastName);

    if (!(cin >> firstName >> lastName)) {
        return 0;
    }
    string result = "";

    result += firstName[0];

    for (int i = 1; i < firstName.length(); i++) {
        if (firstName[i] < lastName[0]) {
            result += firstName[i];
        }
        else {
            break;
        }
    }
    result += lastName[0];

    cout << result << endl;

    return 0;
}