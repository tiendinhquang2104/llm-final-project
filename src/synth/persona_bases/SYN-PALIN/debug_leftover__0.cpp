#include <iostream>
using namespace std;

bool doiXung(long long n) {
    long long goc = n, rev = 0;
    while (n > 0) {
        rev = rev * 10 + n % 10;
        n /= 10;
        // cout << "rev = " << rev << endl;
    }
    // cout << goc << " vs " << rev << endl;
    return rev == goc;
}

int main() {
    long long n;
    cin >> n;
    // cout << doiXung(12321) << endl;
    cout << (doiXung(n) ? "True" : "False");
    return 0;
}
