#include <iostream>
using namespace std;

// so Armstrong: tong cac chu so mu d bang chinh no
bool laArmstrong(int n) {
    int d = 0, x = n;
    while (x > 0) { d++; x /= 10; }
    // cout << "so chu so: " << d << endl;
    long long s = 0;
    x = n;
    while (x > 0) {
        int cs = x % 10;
        long long p = 1;
        for (int i = 0; i < d; i++) p = p * cs;
        // cout << cs << "^" << d << " = " << p << endl;
        s += p;
        x /= 10;
    }
    // cout << "tong = " << s << endl;
    return s == n;
}

int main() {
    int n;
    // n = 153;
    cin >> n;
    if (laArmstrong(n)) cout << "True";
    else cout << "False";
    return 0;
}
