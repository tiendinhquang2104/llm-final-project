#include <iostream>

using namespace std;

int main() {
	int n;
	cin >> n;
	int c = n;

	int a[10] = { 0 };
	int ss = 0;
	for (int i = 0; i < 10; i++) {
		a[i] = n % 10;
		n = n / 10;
		ss++;
		if (n <= 0) break;
	}
	

	int sum = 0;
	int b=1;
	for (int i = 0; i < 10; i++) {
		int b = 1;
		for (int j = 0; j < ss; j++) {
			b *= a[i];
		}
		sum = sum+ b;
	}

	if (sum == c) cout << "True";
	else cout << "False";


	return 0;
}