#include <iostream>
#include <string>
using namespace std;

void vietHoa(string &s) {
    for (int i = 0; i < (int)s.size(); i++) {
        if ('a' <= s[i] && s[i] <= 'z') {
            s[i] = s[i] - ('a' - 'A');
        }
        // cout << i << ": " << s << endl;
    }
}

int main() {
    string s;
    cin >> s;
    vietHoa(s);
    cout << s;
    return 0;
}
