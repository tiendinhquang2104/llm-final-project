#include <iostream>
#include <string>
#include <cctype>
using namespace std;

int main() {
    string s; cin >> s;
    int c = 0;
    for (char ch : s) c += isupper(ch) ? 1 : 0;
    cout << c;
}
