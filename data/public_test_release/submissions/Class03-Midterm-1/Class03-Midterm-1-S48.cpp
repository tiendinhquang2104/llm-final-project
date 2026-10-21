#include <iostream>
using namespace std;

int main() {
	long long n;
	if (!(cin >> n)) return 0;

	long long b=n;
	int d  = 0;
	do
	{
		d++;
		b /= 10;
	} while (b);

	long long sum = 0, a = n;
	do
	{
		int digit = a % 10; 
		long long p = 1;
		for (int i = 0; i < d;++i ) 
			p *= digit;
			sum += p;
			a /= 10;
		

	} while (a);
	cout << (sum == n ? "True" : "False") << endl;
	return 0;
}