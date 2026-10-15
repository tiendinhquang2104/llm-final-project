#include <iostream>
using namespace std;

int tongChuSo(int n) {
    int tong = 0;
    while (n > 0) {
        int cs = n % 10;
        tong = tong + cs;
        n = n / 10;
    }
    return tong;
}

int main() {
    int n;
    cin >> n;
    int t = tongChuSo(n);
    if (t % 3 == 0) {
        cout << "True";
    } else {
        cout << "False";
    }
    return 0;
}
