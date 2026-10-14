#include <iostream>
#include <string>
using namespace std;

bool laNguyenAm(char c) {
    if (c == 'a') return true;
    if (c == 'e') return true;
    if (c == 'i') return true;
    if (c == 'o') return true;
    if (c == 'u') return true;
    return false;
}

int main() {
    string s;
    cin >> s;
    int demNguyenAm = 0;
    int doDai = s.length();
    for (int i = 0; i < doDai; i++) {
        if (laNguyenAm(s[i])) {
            demNguyenAm = demNguyenAm + 1;
        }
    }
    cout << demNguyenAm;
    return 0;
}
