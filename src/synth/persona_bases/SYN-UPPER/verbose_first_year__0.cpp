#include <iostream>
#include <string>
using namespace std;

char chuyenHoa(char c) {
    char ketQua = c;
    if (c >= 'a') {
        if (c <= 'z') {
            ketQua = c - 'a' + 'A';
        }
    }
    return ketQua;
}

int main() {
    string s;
    cin >> s;
    string kq = "";
    for (int i = 0; i < (int)s.length(); i++) {
        kq = kq + chuyenHoa(s[i]);
    }
    cout << kq;
    return 0;
}
