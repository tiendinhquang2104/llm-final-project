#include <iostream>
#include <string>
using namespace std;

int demNguyenAm(string s) {
    int dem = 0;
    for (int i = 0; i < (int)s.size(); i++) {
        char c = s[i];
        if (c == 'a' || c == 'e' || c == 'i' || c == 'o' || c == 'u') {
            dem++;
            // cout << "tim thay " << c << " o vi tri " << i << endl;
        }
    }
    return dem;
}

int main() {
    string s;
    cin >> s;
    // s = "hello";
    cout << demNguyenAm(s);
    return 0;
}
