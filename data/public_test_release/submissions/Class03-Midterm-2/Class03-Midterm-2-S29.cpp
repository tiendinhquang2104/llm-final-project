#include <iostream>
using namespace std;
#define N 10000
void InputArray(int a[N], int& n) {
	cin >> n;
	for (int i = 0; i < n; i++) {
		cin >> a[i];
	}
	cout << n;
}
void OutputArray(int a[N], int n) {
	for (int i = 0; i < n; i++) {
		cout << a[i] << " ";
	}
}
void Soft(int a[N], int n) {
	for (int i = 0; i < n; i++) {
		for (int j = i + 1; j < n; j++) {
			if (a[i] > a[j]) {
				int temp = a[i];
				a[i] = a[j];
				a[j] = temp;
		}
		}
	}
}
//bool is_duplicate(int a[N], int n) {
//	for (int i = 0; i < n; i++) {
//		for (int j = i + 1; j < n; j++) {
//			if (a[i] == a[j]) return true;
//		}
//	}
//}
void UniqueElements(int a[N], int& n) {
 Soft(a,n);
	for (int i = 0; i < n; i++) {
		for (int j = i + 1; j < n; j++) {
			if (a[i] == a[j]) {
			}
		}
	}
}

int main() {
	int a[N], n;
	InputArray(a, n);
	OutputArray(a, n);

	return 0;
}