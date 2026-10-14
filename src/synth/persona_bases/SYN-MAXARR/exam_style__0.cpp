#include <iostream>
#include <climits>
#define ll long long
using namespace std;

int main() {
    int n; cin >> n;
    ll mx = LLONG_MIN;
    for (int i = 0; i < n; i++) { ll x; cin >> x; if (x > mx) mx = x; }
    cout << mx;
}
