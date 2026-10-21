#include <iostream>

using namespace std;


void removeDuplicates(int a[], int& n) {
	for (int i = 0; i < n; i++) {
		for (int j = i + 1; j < n; j++) {
			while (a[i] == a[j]) {
				for (int k = j; k < n; k++) {
					a[k] = a[k + 1];
				}
				n--;
			}
		}
	}
}

int main() {
	int n;
	int a[10000];
	cin >> n;
	for (int i = 0; i < n; i++) {
		cin >> a[i];
	}

	removeDuplicates(a, n);
	cout << n << '\n';
	for (int i = 0; i < n; i++) {
		cout << a[i] << " ";
	}

	return 0;
}
