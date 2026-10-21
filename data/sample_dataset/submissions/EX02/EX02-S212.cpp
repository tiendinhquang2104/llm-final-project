#include <iostream>
using namespace std;



int main() {
	long long n;
	cin >> n;
	long long sum = 0;
	int d = n;
	int numdigi = 0;


	while (n > 0)
	{
		++numdigi;
		n /= 10;

	}
	n = d;
	while (n > 0)
	{
		int digi = n % 10;
		int x = 1;
		for (int i = 1; i <= cnt; i++)
		{
			x *= digi;
		}
		sum += x;
		n /= 10;
	}
	if (sum == d)
		cout << "True";
	else
		cout << "False";


	return 0;
}