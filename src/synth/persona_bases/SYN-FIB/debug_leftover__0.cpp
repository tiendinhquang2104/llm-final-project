#include <iostream>
using namespace std;

long long fib(int n) {
    if (n == 0) return 0;
    long long truoc = 0, sau = 1;
    for (int i = 2; i <= n; i++) {
        long long moi = truoc + sau;
        truoc = sau;
        sau = moi;
        // cout << "F(" << i << ") = " << sau << endl;
    }
    return sau;
}

int main() {
    int n;
    cin >> n;
    // for (int i = 0; i <= 10; i++) cout << fib(i) << " ";
    cout << fib(n);
    return 0;
}
