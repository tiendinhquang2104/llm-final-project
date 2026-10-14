#include <iostream>
#include <string>
#include <algorithm>
using namespace std;

int main() {
    string s, t;
    cin >> s;
    t = s;
    reverse(t.begin(), t.end());
    cout << (s == t ? "True" : "False");
    return 0;
}
