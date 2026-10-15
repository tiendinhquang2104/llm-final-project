#include <iostream>
using namespace std;

int maxMang(int a[], int n) {
    int m = a[0];
    for (int i = 0; i < n; i++) {
        // cout << "a[" << i << "] = " << a[i] << endl;
        if (a[i] > m) m = a[i];
    }
    return m;
}

int main() {
    int n, a[1000];
    cin >> n;
    for (int i = 0; i < n; i++) cin >> a[i];
    // cout << "max: ";
    cout << maxMang(a, n);
    return 0;
}
