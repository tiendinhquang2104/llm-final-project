#include<iostream>

using namespace std;
void main() {
	int n = 1634;
	int a;
	int sum = 0;
	int dem=0;
	int b[50];
	for (int i = 1;; i = i*10) {
		if (n / i > 0)dem++;
		else break;
	}
	cout << dem;
	for (int i = 1000000;i >0; i = i / 10) {
		if (n/i != 0) {
			a = n / i;
			sum += a;
		}
	}
	cout << sum;
}