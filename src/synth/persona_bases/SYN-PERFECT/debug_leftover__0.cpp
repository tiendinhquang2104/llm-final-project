#include <iostream>
using namespace std;

bool isPerfect(int n) {
    if (n <= 1) return false;
    long long sum = 1;
    for (int i = 2; i * i <= n; i++) {
        if (n % i == 0) {
            sum += i;
            if (i * i != n) sum += n / i;
            // cout << "uoc: " << i << " " << n / i << endl;
        }
    }
    // cout << "sum = " << sum << endl;
    return sum == n;
}

int main() {
    int n;
    cin >> n;
    // for (int k = 1; k <= 10000; k++) if (isPerfect(k)) cout << k << " ";
    cout << (isPerfect(n) ? "True" : "False");
    return 0;
}
