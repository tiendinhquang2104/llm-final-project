#include <iostream>
using namespace std;

int gcd(int a, int b) {
    if (b == 0) return a;
    return gcd(b, a % b);
}

int main() {
    int n, a[1000];
    cin >> n;
    for (int i = 0; i < n; i++) cin >> a[i];
    int g = a[0];
    for (int i = 1; i < n; i++) {
        g = gcd(g, a[i]);
        // cout << "gcd sau buoc " << i << ": " << g << endl;
    }
    cout << g;
    return 0;
}
