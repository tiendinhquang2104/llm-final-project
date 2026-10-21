#include <iostream>
using namespace std;
int Pow(int& a, int& d) {
	int power = 1;
	for (int i = 0; i <= d; i++) {
		power *= a;
	}
	return power;
}
int Input(int a) {
	int temp = a;
	int p = 0;
	int sum = 0;
	int n = 0;
	while (a != 0) {
		p = temp % 10;
		temp /= 10;
		n++;
		sum += Pow(p, n);
	}
	return sum;
}
bool is_armstrong_number(int& a) {
	Input(a);
	if (Input(a)== a) return true;
}
int main() {
	int a;
	cin >> a;
	if (is_armstrong_number) cout << "True";

}