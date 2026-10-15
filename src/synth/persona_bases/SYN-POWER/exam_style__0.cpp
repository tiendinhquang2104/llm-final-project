#include <iostream>
#define ll long long
using namespace std;

ll bp(ll a, ll b) {
    ll r = 1;
    while (b) { if (b & 1) r *= a; a *= a; b >>= 1; }
    return r;
}

int main() {
    ll a, b; cin >> a >> b;
    cout << bp(a, b);
}
