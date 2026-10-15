#include <iostream>
using namespace std;

int ucln(int a, int b) {
    while (a != b) {
        if (a > b) {
            a = a - b;
        } else {
            b = b - a;
        }
    }
    return a;
}

int main() {
    int n;
    cin >> n;
    int mang[1000];
    for (int i = 0; i < n; i++) {
        cin >> mang[i];
    }
    int ketQua = mang[0];
    for (int i = 1; i < n; i++) {
        ketQua = ucln(ketQua, mang[i]);
    }
    cout << ketQua;
    return 0;
}
