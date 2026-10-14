#include <iostream>
#include <string>
using namespace std;

string daoChuoi(string s) {
    string ketQua = "";
    int doDai = s.length();
    int viTri = doDai - 1;
    while (viTri >= 0) {
        ketQua = ketQua + s[viTri];
        viTri = viTri - 1;
    }
    return ketQua;
}

int main() {
    string s;
    cin >> s;
    string kq = daoChuoi(s);
    cout << kq;
    return 0;
}
