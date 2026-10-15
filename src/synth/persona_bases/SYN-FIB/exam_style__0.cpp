#include <iostream>
#define ll long long
using namespace std;

ll memo[100];
ll fib(int n) {
    if (n < 2) return n;
    if (memo[n]) return memo[n];
    return memo[n] = fib(n - 1) + fib(n - 2);
}

int main() {
    int n; cin >> n;
    cout << fib(n);
}
