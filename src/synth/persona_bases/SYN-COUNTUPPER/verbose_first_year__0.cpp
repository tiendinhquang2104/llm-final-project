#include <iostream>
#include <string>
using namespace std;

bool laChuHoa(char c) {
    if (c >= 'A' && c <= 'Z') {
        return true;
    }
    return false;
}

int main() {
    string s;
    cin >> s;
    int soChuHoa = 0;
    int i = 0;
    while (i < (int)s.length()) {
        if (laChuHoa(s[i]) == true) {
            soChuHoa = soChuHoa + 1;
        }
        i = i + 1;
    }
    cout << soChuHoa;
    return 0;
}
