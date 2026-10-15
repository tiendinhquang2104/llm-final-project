#include <iostream>
using namespace std;

long long luyThua(long long a, int b) {
    if (b == 0) return 1;
    long long half = luyThua(a, b / 2);
    // cout << "a^" << b / 2 << " = " << half << endl;
    if (b % 2 == 0) return half * half;
    return half * half * a;
}

int main() {
    long long a;
    int b;
    cin >> a >> b;
    cout << luyThua(a, b);
    return 0;
}
