#include <iostream>
#include <string>
#define ll long long
using namespace std;

ll mu(int a, int b) {
    ll r = 1;
    while (b--) r *= a;
    return r;
}

int main() {
    ll n; cin >> n;
    string s = to_string(n);
    int d = s.size();
    ll sum = 0;
    for (char c : s) sum += mu(c - '0', d);
    cout << (sum == n ? "True" : "False");
    return 0;
}
