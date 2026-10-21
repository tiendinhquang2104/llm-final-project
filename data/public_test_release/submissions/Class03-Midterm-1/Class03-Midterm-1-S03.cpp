#include <iostream>
using namespace std;
bool check(int n) {
	int tong = 0;
	int tmp = n;
	int count = 0;
	while (tmp > 0) {
		count++;
		tmp /= 10;
	}
	tmp = n;
	while (tmp > 0) {
		int i = tmp % 10;
		int t = i;
		for (int k = 1; k < count; k++) {
			i *= t;
		}
		tong += i;
		tmp /= 10;
	}
	if (tong == n) return true;
	else return false;
}
int main() {
	int n;
	cin >> n;
	if (check(n)) cout << "True";
	else cout << "False";
	return 0;
}