#include <iostream>
using namespace std;

long long tongChan(int a[], int n) {
    long long s = 0;
    for (int i = 0; i < n; i++) {
        if (a[i] % 2 == 0) {
            s += a[i];
            // cout << "cong " << a[i] << endl;
        }
    }
    return s;
}

int main() {
    int n, a[1000];
    cin >> n;
    for (int i = 0; i < n; i++) cin >> a[i];
    // cout << "n = " << n << endl;
    cout << tongChan(a, n);
    return 0;
}
