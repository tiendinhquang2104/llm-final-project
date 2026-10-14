#include <iostream>
using namespace std;

bool isPrime(long long n) {
    if (n <= 1) return false;
    for (long long i = 2; i * i <= n; i++) {
        // cout << "thu chia cho " << i << endl;
        if (n % i == 0) return false;
    }
    return true;
}

int main() {
    long long n;
    cin >> n;
    // for (int k = 1; k < 30; k++) cout << k << ": " << isPrime(k) << endl;
    if (isPrime(n)) cout << "True";
    else cout << "False";
    return 0;
}
