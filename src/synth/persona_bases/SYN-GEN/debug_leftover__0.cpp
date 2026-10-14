#include <iostream>
#include <fstream>
#include <vector>
#include <string>
using namespace std;

struct Rec { int a, b; };

Rec* prob1(string filename, int& n) {
    ifstream f(filename);
    // if (!f.is_open()) cout << "khong mo duoc file" << endl;
    vector<Rec> v;
    Rec r;
    while (f >> r.a >> r.b) {
        v.push_back(r);
    }
    n = v.size();
    Rec* arr = new Rec[n + 1];
    for (int i = 0; i < n; i++) arr[i] = v[i];
    // for (int i = 0; i < n; i++) cout << arr[i].a << " " << arr[i].b << endl;
    return arr;
}

int prob2(Rec* arr, int n) {
    int s = 0;
    for (int i = 0; i < n; i++) {
        s += arr[i].a;
        // cout << "i = " << i << " s = " << s << endl;
    }
    return s;
}

int prob3(Rec* arr, int n) {
    int res = arr[0].a;
    for (int i = 0; i < n; i++) {
        if (arr[i].a > res) res = arr[i].a;
    }
    // cout << "ket qua: " << res << endl;
    return res;
}

void prob4(Rec* arr, int n) {
    // goi lai cau 2
    cout << prob2(arr, n);
}

// int main() {
//     int n;
//     Rec* a = prob1("data.csv", n);
//     prob4(a, n);
// }
