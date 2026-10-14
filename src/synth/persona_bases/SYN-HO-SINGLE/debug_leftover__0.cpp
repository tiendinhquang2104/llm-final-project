#include <iostream>
using namespace std;

bool chiaHet3(long long n) {
    int s = 0;
    while (n > 0) {
        s += n % 10;
        n /= 10;
    }
    // cout << "tong chu so = " << s << endl;
    return s % 3 == 0;
}

int main() {
    long long n;
    cin >> n;
    // cout << chiaHet3(123) << " " << chiaHet3(124) << endl;
    cout << (chiaHet3(n) ? "True" : "False");
    return 0;
}
