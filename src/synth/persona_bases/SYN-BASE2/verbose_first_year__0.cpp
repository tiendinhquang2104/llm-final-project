#include <iostream>
using namespace std;

int main() {
    long long n;
    cin >> n;
    int mangBit[64];
    int soBit = 0;
    if (n == 0) {
        cout << 0;
        return 0;
    }
    while (n > 0) {
        mangBit[soBit] = n % 2;
        soBit = soBit + 1;
        n = n / 2;
    }
    // in nguoc lai tu bit cao nhat
    for (int i = soBit - 1; i >= 0; i--) {
        cout << mangBit[i];
    }
    return 0;
}
