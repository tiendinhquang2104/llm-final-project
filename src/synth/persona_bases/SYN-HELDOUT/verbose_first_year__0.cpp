#include <iostream>
using namespace std;

// tim uoc chung lon nhat bang thuat toan Euclid
int timUCLN(int a, int b) {
    int soDu;
    if (a == 0) {
        return b;
    }
    if (b == 0) {
        return a;
    }
    while (b != 0) {
        soDu = a % b;
        a = b;
        b = soDu;
    }
    return a;
}

int main() {
    int a, b;
    cin >> a >> b;
    int ketQua = timUCLN(a, b);
    cout << ketQua;
    return 0;
}
