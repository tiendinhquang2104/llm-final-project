#include <iostream>
#include <string>
#include <algorithm>
#define ll long long
using namespace std;

int main() {
    ll n; cin >> n;
    string s;
    if (!n) s = "0";
    while (n) { s += char('0' + (n & 1)); n >>= 1; }
    reverse(s.begin(), s.end());
    cout << s;
}
