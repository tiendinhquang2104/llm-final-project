#include <iostream>

using namespace std;

int main() {

	int n, mod;
	int sum = 0;
	int cnt = 0;

	cin >> n;

	if (n < 1 || n > 1e9) {
		cout << "Invalid";
		return 0;
	}


	while (n != 0) {
		mod = n % 10;
		n /= 10;
		cnt++;
	}

	while (n != 0) {
		mod = n % 10;
		n /= 10;
		sum += mod ^ cnt;
	}
	
	if (sum == n)
		cout << "True";
	else
		cout << "False";


	return 0;
}
