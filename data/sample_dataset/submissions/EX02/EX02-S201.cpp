#include <iostream>

using namespace std;

void ArmstrongNumber(int n) {
	if (n < 1 || n > 10e9) return;
	int intTemp1 = n, intTemp2 = n;
	int sum = 0;
	int count = 0;
	while (intTemp1 != 0) {
		int a = intTemp1 % 10;
		intTemp1 /= 10;
		count++;
	}
	while (intTemp2 != 0) {
		int a = intTemp2 % 10;
		int tich = 1;
		for (int i = 0; i < count; i++) {
			tich *= a;
		}
		sum += tich;
		intTemp2 /= 10;
	}
	if (sum == n) cout << "True\n";
	else cout << "False\n";
}

int main() {
	int n;
	cin >> n;
	ArmstrongNumber(n);
	return 0;
}