#include <iostream>
using namespace std;
int ts(int n) {
    int dem = 0;
    while (n != 0) {
        ++dem;
        n /= 10;
    }

}
bool Sum (long long n) {
    int res = 0, dem = ts(n);
    const int temp = n;
    while (n != 0) {
        res = res + (n % 10)*dem;
        n /= 10;
    }
    if (res == temp) return true;
    else return false;
}

int main () {
    long long n; cin >> n;
    if (Sum(n) == true) cout << "TRUE";
    else cout << "FALSE";
    return 0;

}
