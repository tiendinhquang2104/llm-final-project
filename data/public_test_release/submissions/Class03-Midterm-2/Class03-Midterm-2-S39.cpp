#include <iostream>
using namespace std;

int main() {
	int n;
	cin >> n;

	int n1 = n;
	int a[10000];
	for (int i = 0; i < n; i++) {
		cin >> a[i];
	}


	
	for (int i = 0; i < n; i++) {
		for (int j = i + 1; j < n; j++) {
			if (a[i] == a[j]) {
				a[j] = 0;
			}
		}
	}

	for (int i = 0; i < n; i++) {
		if (a[i] == 0) n1--;
	}

	cout << n1 << endl;
	for (int i = 0; i < n; i++) {
		if (a[i] != 0)cout << a[i]<<" ";
	}
	

	return 0;
}