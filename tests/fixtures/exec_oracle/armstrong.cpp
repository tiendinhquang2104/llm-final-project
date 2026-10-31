#include <iostream>
using namespace std;
int main() { long long n; cin >> n; int d = 0; for (long long t = n; t > 0; t /= 10) d++;
    long long s = 0; for (long long t = n; t > 0; t /= 10) { long long p = 1; for (int i = 0; i < d; i++) p *= t % 10; s += p; }
    cout << (s == n ? "True" : "False") << endl; }
