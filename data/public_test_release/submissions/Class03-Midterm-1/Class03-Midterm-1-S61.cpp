#include <iostream>

unsigned long long digits[15];

unsigned long long luy_thua(unsigned long long a, unsigned long long n) {
    unsigned long long ket_qua = 1;
    for (int i = 1; i <= n; i++) {
        ket_qua *= a;
    }

    return ket_qua;
}

int main() {
    unsigned long long n;
    std::cin >> n;

    unsigned long long temp = n, d = 0, sum = 0;

    while (temp != 0) {
        digits[d] = temp % 10;
        temp /= 10;
        d++;
    }

    for (int i = 0; i < d; i++) {
        sum += luy_thua(digits[i], d);
    }

    if (sum == n) {
        std::cout << "True";
        return 0;
    }

    std::cout << "False";
    return 0;
}
