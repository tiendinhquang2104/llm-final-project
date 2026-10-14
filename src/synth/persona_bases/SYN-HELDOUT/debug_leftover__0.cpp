#include <iostream>
using namespace std;

int ucln(int a, int b) {
    // cout << "a = " << a << " b = " << b << endl;
    while (b > 0) {
        int r = a % b;
        a = b;
        b = r;
        // cout << "-> " << a << " " << b << endl;
    }
    return a;
}

int main() {
    int a, b;
    cin >> a >> b;
    // test: ucln(12, 18) = 6
    cout << ucln(a, b);
    return 0;
}
