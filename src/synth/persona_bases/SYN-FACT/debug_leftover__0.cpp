#include <iostream>
using namespace std;

long long giaiThua(int n) {
    long long r = 1;
    for (int i = 2; i <= n; i++) {
        r = r * i;
        // cout << i << "! = " << r << endl;
    }
    return r;
}

int main() {
    int n;
    cin >> n;
    // n = 20; // gioi han long long
    cout << giaiThua(n);
    return 0;
}
