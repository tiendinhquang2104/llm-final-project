#include <iostream>
using namespace std;

// kiem tra x da xuat hien trong mang a[0..k-1] chua
bool daXuatHien(int a[], int k, int x) {
    for (int i = 0; i < k; i++) {
        if (a[i] == x) {
            return true;
        }
    }
    return false;
}

int main() {
    int n;
    cin >> n;
    int mang[1000];
    for (int i = 0; i < n; i++) {
        cin >> mang[i];
    }
    int soPhanBiet = 0;
    for (int i = 0; i < n; i++) {
        if (daXuatHien(mang, i, mang[i]) == false) {
            soPhanBiet = soPhanBiet + 1;
        }
    }
    cout << soPhanBiet;
    return 0;
}
