#include <iostream>
using namespace std;

// Kiem tra so Armstrong
int demChuSo(int x) {
    int dem = 0;
    if (x == 0) {
        dem = 1;
    } else {
        while (x != 0) {
            x = x / 10;
            dem = dem + 1;
        }
    }
    return dem;
}

long long luyThua(int coSo, int soMu) {
    long long ketQua = 1;
    int i = 1;
    while (i <= soMu) {
        ketQua = ketQua * coSo;
        i = i + 1;
    }
    return ketQua;
}

int main() {
    int n;
    cin >> n;
    int soChuSo = demChuSo(n);
    int tam = n;
    long long tong = 0;
    while (tam > 0) {
        int chuSo = tam % 10;
        long long giaTri = luyThua(chuSo, soChuSo);
        tong = tong + giaTri;
        tam = tam / 10;
    }
    if (tong == n) {
        cout << "True";
    } else {
        cout << "False";
    }
    return 0;
}
