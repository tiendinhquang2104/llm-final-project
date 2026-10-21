#include <iostream>
using namespace std;

int powOfDigits(int num, int d) {
	int power = 1;
	for (int i = 1; i <= d; i++) {
		power *= num;
	}
	return power;
}

long long isArmstrong(int n) {
	int armstrongCheck = 0;
	int countDigits = 0;
	int temp = n;

	while (temp > 0) {
		temp /= 10;
		countDigits++;
	}
	while (n > 0) {
		int digits = n % 10;
		armstrongCheck += powOfDigits(digits, countDigits);
		n /= 10;
	}
	return armstrongCheck;
}

int main() {
	long long n;
	cin >> n;
	
	if (n == isArmstrong(n)) {
		cout << "True" << endl;
	}
	else cout << "False" << endl;

	return 0;
}