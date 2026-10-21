#include <iostream>
#include <string>
using namespace std;

int main() {
     string firstName, lastName;
     cin >> firstName >> lastName;
     string minUsername = firstName + lastName;
     int n = firstName.length();
     int m = lastName.length();
     for (int i = 1; i <= n; i++) {
         for (int j = 1; j <= m; j++) {
             string username = firstName.substr(0, i) + lastName.substr(0, j);
                if (username < minUsername) {
                    minUsername = username;
                }
         }
     }
     cout << minUsername << '\n';
  return 0;
}