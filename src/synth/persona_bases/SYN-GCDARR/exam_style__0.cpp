#include <iostream>
#define ll long long
using namespace std;

ll g(ll a, ll b) { return b ? g(b, a % b) : a; }

int main() {
    int n; cin >> n;
    ll r = 0;
    for (int i = 0; i < n; i++) { ll x; cin >> x; r = g(r, x); }
    cout << r;
}
