#include <iostream>
#include <climits>
#define ll long long
using namespace std;

int main() {
    int n; cin >> n;
    ll m1 = LLONG_MIN, m2 = LLONG_MIN;
    for (int i = 0; i < n; i++) {
        ll x; cin >> x;
        if (x > m1) { m2 = m1; m1 = x; }
        else if (x > m2) m2 = x;
    }
    cout << m2;
}
