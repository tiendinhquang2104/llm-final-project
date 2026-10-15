#include <iostream>
using namespace std;

// tinh tong cac uoc thuc su cua n (khong tinh chinh n)
long long tongUoc(int n) {
    long long tong = 0;
    if (n == 1) {
        return 0;
    }
    tong = 1;
    for (int i = 2; (long long)i * i <= n; i++) {
        if (n % i == 0) {
            tong = tong + i;
            int uocKia = n / i;
            if (uocKia != i) {
                tong = tong + uocKia;
            }
        }
    }
    return tong;
}

int main() {
    int n;
    cin >> n;
    long long t = tongUoc(n);
    bool hoanHao = false;
    if (t == n) {
        hoanHao = true;
    }
    if (hoanHao == true) {
        cout << "True";
    } else {
        cout << "False";
    }
    return 0;
}
