#include<iostream>
using namespace std;
void input(long long &n) {
	cin >> n;
}
long long Pow(int digits, long long cnt) {
	long long res = 1;
	for (int i = 0; i < cnt; i++) res = res * digits;
	return res;
}
bool isArmstrong(long long n) {
	long long sum = 0;
	int cnt = 0;
	long long tem1 = n;
	long long tem2 = n;
	while (tem1 > 0) {
		cnt++;
		tem1 /= 10;
	}
	while (tem2 > 0) {
		int digits = tem2 % 10;
		sum += Pow(digits, cnt);
		tem2 /= 10;
	}
	if (sum == n) return true;
	else return false;
}
void output(long long n) {
	if (isArmstrong(n)) cout << "True";
	else cout << "False";
}
int main() {
	long long n;
	input(n);
	output(n);
}