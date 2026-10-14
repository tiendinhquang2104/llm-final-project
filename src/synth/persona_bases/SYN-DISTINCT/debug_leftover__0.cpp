#include <iostream>
using namespace std;

int demPhanBiet(int a[], int n) {
    int dem = 0;
    for (int i = 0; i < n; i++) {
        int j = 0;
        while (j < i && a[j] != a[i]) j++;
        if (j == i) dem++;
        // cout << "i = " << i << " dem = " << dem << endl;
    }
    return dem;
}

int main() {
    int n, a[1000];
    cin >> n;
    for (int i = 0; i < n; i++) cin >> a[i];
    // for (int i = 0; i < n; i++) cout << a[i] << " ";
    cout << demPhanBiet(a, n);
    return 0;
}
