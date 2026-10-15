#include <iostream>
#include <string>
using namespace std;

int demHoa(string s) {
    int dem = 0;
    for (int i = 0; i < (int)s.size(); i++) {
        if (s[i] >= 'A' && s[i] <= 'Z') {
            dem++;
        }
        // else cout << s[i] << " khong phai chu hoa" << endl;
    }
    return dem;
}

int main() {
    string s;
    cin >> s;
    cout << demHoa(s);
    // cout << endl << "do dai: " << s.size();
    return 0;
}
