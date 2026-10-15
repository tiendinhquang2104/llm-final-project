#include <iostream>
using namespace std;

int timLonNhat(int a[], int n) {
    int lonNhat = a[0];
    int viTri = 0;
    for (int i = 1; i < n; i++) {
        if (a[i] > lonNhat) {
            lonNhat = a[i];
            viTri = i;
        }
    }
    return lonNhat;
}

int main() {
    int n;
    cin >> n;
    int mang[1000];
    for (int i = 0; i < n; i++) {
        cin >> mang[i];
    }
    int kq = timLonNhat(mang, n);
    cout << kq;
    return 0;
}
