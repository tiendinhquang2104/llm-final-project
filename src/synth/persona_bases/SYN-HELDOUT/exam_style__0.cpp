#include <iostream>
#define ll long long
using namespace std;

ll g(ll a, ll b) { return b == 0 ? a : g(b, a % b); }

int main() {
    ll a, b; cin >> a >> b;
    cout << g(a, b);
}
