#include <iostream>
using namespace std;

int main() {
    int n;
    cin >> n;
    int a[1000];
    for (int i = 0; i < n; i++) {
        cin >> a[i];
    }
    // tim so lon nhat truoc
    int lonNhat = a[0];
    for (int i = 1; i < n; i++) {
        if (a[i] > lonNhat) {
            lonNhat = a[i];
        }
    }
    // tim so lon nhat trong cac so nho hon lonNhat
    bool daCo = false;
    int lonNhi = 0;
    for (int i = 0; i < n; i++) {
        if (a[i] < lonNhat) {
            if (daCo == false || a[i] > lonNhi) {
                lonNhi = a[i];
                daCo = true;
            }
        }
    }
    cout << lonNhi;
    return 0;
}
