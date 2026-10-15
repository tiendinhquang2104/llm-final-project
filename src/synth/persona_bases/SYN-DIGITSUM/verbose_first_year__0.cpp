#include <iostream>
using namespace std;

int tinhTongChuSo(int n) {
    int tong = 0;
    int chuSo;
    if (n == 0) {
        return 0;
    }
    while (n > 0) {
        chuSo = n % 10;
        tong = tong + chuSo;
        n = n / 10;
    }
    return tong;
}

int main() {
    int n;
    cin >> n;
    int ketQua;
    ketQua = tinhTongChuSo(n);
    cout << ketQua;
    return 0;
}
