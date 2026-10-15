#include <iostream>
#include <string>
using namespace std;

int main() {
    string s; cin >> s;
    string v = "aeiou";
    int c = 0;
    for (char ch : s) if (v.find(ch) != string::npos) c++;
    cout << c;
}
