#include <iostream>
using namespace std;

const int MAX = 50;

int countDigit(int n, int& a) {
	while (n != 0) {
		n /= 10;
		a++;
	}
	return a;
}

bool checkArmstrong(int a[], int b[], int n, int digit) {
	int j = 0;
	int startNum = n;
	while (n != 0) {
		a[j] = n % 10;
		n /= 10;
		j++;
	}
	for (int i = 0; i < digit; i++) {
		b[i] = a[i];
	}

	for (int i = 0; i < digit; i++) {
		for (int j = 0; j < digit-1; j++) {
			b[i] *= a[i];
		}
	}

	int sum = 0;
	for (int i = 0; i < digit; i++) {
		sum += b[i];
	}

	if (startNum == sum) return 1;
	return 0;
}


int main() {
	int n, digit=0;
	cin >> n;
	countDigit(n, digit);	
	int a[MAX], b[MAX];

	if (checkArmstrong(a, b, n, digit)) cout << "True";
	else cout << "False";
	return 0;
}