#include <iostream>
using namespace std;

int notHashing(int x) {
	return x % 10000;
}
int a[10000];
int b[10000];
int main() {
	int n; cin >> n;
	for (int i = 0; i < 10000; ++i) {
		b[i] = -2e9;
	}
	int cnt = 0;
	for (int i = 0; i < n; ++i) {
		cin >> a[i];
		int t = notHashing(a[i]);
		if (b[t] == a[i]) continue;
		for (int j = 0; j < 10000; ++j) {
			if (b[t] != -2e9) t = (t + 1) % 10000;
			else break;
		}
		if (b[t] == -2e9) {
			++cnt;
			b[t] = a[i];
		}
	}
	
	cout << cnt << '\n';
	for (int i = 0; i < n; ++i) {
		int x = notHashing(a[i]);
		if (b[x] == a[i]) {
			cout << a[i] << ' ';
			b[x] = -2e9;
		}
		else {
			for (int j = 0; j < 10000; ++j) {
				if (b[x] != a[i]) x = (x + 1) % 10000;
				else break;
			}
			if (b[x] == a[i]) {
				cout << a[i] << ' ';
				b[x] = -2e9;
			}
		}
	}
}
