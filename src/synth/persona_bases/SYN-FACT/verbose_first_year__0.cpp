#include <iostream>
using namespace std;

long long tinhGiaiThua(int n) {
    long long ketQua = 1;
    if (n == 0) {
        return 1;
    }
    if (n == 1) {
        return 1;
    }
    int i = 1;
    while (i <= n) {
        ketQua = ketQua * i;
        i = i + 1;
    }
    return ketQua;
}

int main() {
    int n;
    cin >> n;
    cout << tinhGiaiThua(n);
    return 0;
}
