#include <iostream>
using namespace std;

// kiem tra so nguyen to
bool kiemTraNguyenTo(int n) {
    if (n < 2) {
        return false;
    }
    if (n == 2) {
        return true;
    }
    if (n % 2 == 0) {
        return false;
    }
    long long i = 3;
    while (i * i <= n) {
        if (n % i == 0) {
            return false;
        }
        i = i + 2;
    }
    return true;
}

int main() {
    int n;
    cin >> n;
    bool laNguyenTo = kiemTraNguyenTo(n);
    if (laNguyenTo) {
        cout << "True";
    } else {
        cout << "False";
    }
    return 0;
}
