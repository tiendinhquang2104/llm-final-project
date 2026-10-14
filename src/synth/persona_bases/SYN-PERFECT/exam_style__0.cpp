#include <iostream>
#define ll long long
using namespace std;

bool ok(ll n) {
    if (n < 2) return false;
    ll s = 1;
    for (ll i = 2; i * i <= n; i++)
        if (n % i == 0) { s += i; if (i != n / i) s += n / i; }
    return s == n;
}

int main() {
    ll n; cin >> n;
    cout << (ok(n) ? "True" : "False");
}
