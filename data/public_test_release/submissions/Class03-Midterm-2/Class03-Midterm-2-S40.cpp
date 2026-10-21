#include <iostream>
using namespace std;

int main() {
    int n;
    if (!(cin >> n)) return 0;
    cout << "Input size of array and n integers: ";
    long long a[10000];
    int m = 0;

    for (int i = 0; i < n; ++i) {
        long long x;
        cin >> x;
        bool seen = false;
        for (int j = 0; j < m; ++j) {
            if (a[j] == x) { seen = true; break; }
        }
        if (!seen) a[m++] = x;
    }

    cout << m << endl;
    for (int i = 0; i < m; ++i) {
        if (i) cout << ' ';
        cout << a[i];
    }
    cout << endl;
    return 0;
}