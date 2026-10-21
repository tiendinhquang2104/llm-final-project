#include <iostream>
using namespace std;


int Luythuy(int n, int k){
	int kq = 1;
	if (k % 2 == 0) {
		for (int i = 1; i < k; i++) {
			n = n * n;
		}
	}
	else {
		for (int i = 1; i < k; i++) {
			int temp = n;
			kq = kq * n;
		}
	}
	return kq;
}
int Amstrongnum(int n) {
	int num = 1;
	int temp = 0;
	int res = 0;
	int t[100];
	int m = n;
	while (m > 0){
			temp = m % 10;
			num++;
			m = m / 10;
	}
	int somoi = num;
	int cur = 0;
	while (n > 0) {
		cur = n % 10;
		n = n / 10;
		res += Luythuy(cur, somoi);
	}
	return res;
}
int main() {
	int n;
	cin >> n;
	int kqcuoi = Amstrongnum(n);
	if (kqcuoi == n) {
		cout << "True";
	}
	else {
		cout << "False";
	}
	return 0;
}