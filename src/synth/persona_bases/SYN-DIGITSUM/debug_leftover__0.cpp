#include <iostream>
using namespace std;

int main() {
    long long n;
    cin >> n;
    int s = 0;
    // int dem = 0;
    while (n > 0) {
        s += n % 10;
        // cout << "chu so: " << n % 10 << endl;
        n /= 10;
        // dem++;
    }
    // cout << "so chu so = " << dem << endl;
    cout << s;
    return 0;
}
