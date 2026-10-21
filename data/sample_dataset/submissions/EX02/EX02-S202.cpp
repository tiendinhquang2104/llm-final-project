
#include <iostream>
using namespace std;

int powNum(int a, int n) {
    int res = 1;
    for (int i = 0; i < n; i++) {
        res *= a;
    }
    return res;
}

int lenDigits(int n) {
    int idx = 0;
    while (n > 0) {
        n /= 10;
        idx++;
    }
    return idx;
}
void printDigit(int n) {
    while (n > 0) {
        int du = n % 10;
        cout << du << " ";
        n /= 10;
    }
}

bool checkArmstrongNumber(int n) {
    int num = n;
    int sumDigits = 0;
    int idx = lenDigits(n);
    while (num > 0) {
        int du = num % 10;
        sumDigits += powNum(du, idx);
        num /= 10;
    }
    if (sumDigits == n) return true;
    return false;
}
int main()
{
    int n;
    cin >> n;
    if (checkArmstrongNumber(n) == true) cout << "True" << endl;
    else cout << "False" << endl;
    return 0;
}
