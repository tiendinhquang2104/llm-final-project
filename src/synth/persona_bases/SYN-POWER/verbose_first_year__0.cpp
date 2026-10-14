#include <iostream>
using namespace std;

long long tinhLuyThua(long long coSo, int soMu) {
    long long ketQua = 1;
    if (soMu == 0) {
        return 1;
    }
    for (int lan = 1; lan <= soMu; lan++) {
        ketQua = ketQua * coSo;
    }
    return ketQua;
}

int main() {
    long long a;
    int b;
    cin >> a >> b;
    long long kq = tinhLuyThua(a, b);
    cout << kq;
    return 0;
}
