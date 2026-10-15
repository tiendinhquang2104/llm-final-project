#include <iostream>
#define ll long long
using namespace std;

int main() {
    ll n; cin >> n;
    int s = 0;
    for (; n; n /= 10) s += n % 10;
    cout << (s % 3 ? "False" : "True");
}
