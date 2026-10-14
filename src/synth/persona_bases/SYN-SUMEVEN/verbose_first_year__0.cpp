#include <iostream>
using namespace std;

bool laSoChan(int x) {
    if (x % 2 == 0) {
        return true;
    } else {
        return false;
    }
}

int main() {
    int n;
    cin >> n;
    int a[1000];
    int i = 0;
    while (i < n) {
        cin >> a[i];
        i = i + 1;
    }
    long long tongChan = 0;
    for (int k = 0; k < n; k++) {
        if (laSoChan(a[k]) == true) {
            tongChan = tongChan + a[k];
        }
    }
    cout << tongChan;
    return 0;
}
