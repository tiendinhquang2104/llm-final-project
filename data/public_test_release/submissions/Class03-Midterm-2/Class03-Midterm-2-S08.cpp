#include <iostream>
using namespace std;
#define N 100

void Input(int a[N], int&n) {
	cout << "Input an integer n: ";
	cin >> n;
	for (int i = 0; i < n; i++) {
		cin >> a[i];
	}
}

void Output(int a[N], int n) {
	for (int i = 0; i < n; i++) {
		cout << a[i] << " ";
	}
}

void CheckUnique(int a[N], int n, int b[N], int&k) {
	for (int i = 0; i < n; i++) {
		if (a[i + 1] == a[i]) {
			a[i + 1] = a[i + 2];
			n--;
		}
		b[k++] = a[i];
	}
	for (int j = 0; j < k; j++) {
		a[j] = b[j];
	}
}

int main() {
	int a[N], b[N], n, k;
	Input(a, n);
	CheckUnique(a, n, b, k);
	Output(a, n);
	return 0;
}