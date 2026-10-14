#include <iostream>
using namespace std;

long long fibonacci(int n) {
    long long f[100];
    f[0] = 0;
    f[1] = 1;
    for (int i = 2; i <= n; i++) {
        f[i] = f[i - 1] + f[i - 2];
    }
    return f[n];
}

int main() {
    int n;
    cin >> n;
    long long ketQua = fibonacci(n);
    cout << ketQua;
    return 0;
}
