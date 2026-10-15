#include <iostream>
#define ll long long
using namespace std;

int main() {
    int n; cin >> n;
    ll s = 0;
    while (n--) { ll x; cin >> x; if (!(x & 1)) s += x; }
    cout << s;
}
