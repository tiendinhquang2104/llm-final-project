#include <iostream>
#include <string>
using namespace std;

string doiNhiPhan(long long n) {
    if (n == 0) return "0";
    string r = "";
    while (n > 0) {
        // cout << n << " % 2 = " << n % 2 << endl;
        r = char('0' + n % 2) + r;
        n /= 2;
    }
    return r;
}

int main() {
    long long n;
    cin >> n;
    // cout << doiNhiPhan(10) << endl; // 1010
    cout << doiNhiPhan(n);
    return 0;
}
