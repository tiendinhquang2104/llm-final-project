#include <iostream>

using namespace std;

long long n;

long long gt(int x, int n) {
	long long tmp = 1;

	for (int i = 1; i <=n; ++i) tmp *= x;

	return tmp;
}

int main() {
	cin >> n;

	long long sum = 0, m = n, t = n;
	int i = 0;

	while (m != 0) {
		int tmp = m % 10;
		m /= 10;

		++i;
	}

	while (n != 0) {
		int tmp = n % 10;
		n /= 10;

		sum += gt(tmp, i);
	}

	if (sum == t) cout << "True\n";
	else cout << "False\n";

	return 0;
}