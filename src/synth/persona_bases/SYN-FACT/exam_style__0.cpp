#include <iostream>
#define ll long long
using namespace std;

ll f(int n) { return n <= 1 ? 1 : n * f(n - 1); }

int main() {
    int n; cin >> n;
    cout << f(n);
}
