#include <iostream>
#include <string>
using namespace std;

void dao(string &s) {
    int l = 0, r = s.size() - 1;
    while (l < r) {
        char t = s[l];
        s[l] = s[r];
        s[r] = t;
        // cout << "doi " << l << " va " << r << ": " << s << endl;
        l++;
        r--;
    }
}

int main() {
    string s;
    cin >> s;
    dao(s);
    cout << s;
    return 0;
}
