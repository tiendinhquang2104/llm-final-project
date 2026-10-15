#include <iostream>
using namespace std;

// dao nguoc so n
long long daoNguoc(long long n) {
    long long ketQua = 0;
    while (n > 0) {
        int chuSoCuoi = n % 10;
        ketQua = ketQua * 10 + chuSoCuoi;
        n = n / 10;
    }
    return ketQua;
}

int main() {
    long long n;
    cin >> n;
    long long soDao = daoNguoc(n);
    if (n == 0) {
        cout << "True";
    } else if (soDao == n) {
        cout << "True";
    } else {
        cout << "False";
    }
    return 0;
}
