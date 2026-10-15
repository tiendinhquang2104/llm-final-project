#include <iostream>
using namespace std;

int lonThuHai(int a[], int n) {
    int max1, max2;
    if (a[0] > a[1]) { max1 = a[0]; max2 = a[1]; }
    else { max1 = a[1]; max2 = a[0]; }
    for (int i = 2; i < n; i++) {
        if (a[i] > max1) {
            max2 = max1;
            max1 = a[i];
        } else if (a[i] > max2) {
            max2 = a[i];
        }
        // cout << "max1 = " << max1 << " max2 = " << max2 << endl;
    }
    return max2;
}

int main() {
    int n, a[1000];
    cin >> n;
    for (int i = 0; i < n; i++) cin >> a[i];
    cout << lonThuHai(a, n);
    return 0;
}
