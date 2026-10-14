#include <iostream>
#define ll long long
using namespace std;

int f(ll n) { return n < 10 ? n : n % 10 + f(n / 10); }

int main() {
    ll n; cin >> n;
    cout << f(n);
}
