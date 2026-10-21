#include <iostream>
using namespace std;

void Armstrong(long long& n) {
	cout << "Input n: ";
	cin >> n;
	int d = 0;
	int tam1 = n;
	int k = 0;
	int j = n;
	int tam3 = 0;
	while (n != 0) {
		d = d + 1;
		n /= 10;
	}
	while (tam1 != 0) {
		tam3 = tam1 % 10;
		int tam2 = pow(tam3, d);
		k = tam2 + k;
		tam1 /= 10;
	}
	
	if (k == j) { cout << "True"; }
	else cout << "False";
}

int main() {
	long long n;
	Armstrong(n);
	return 0;
}