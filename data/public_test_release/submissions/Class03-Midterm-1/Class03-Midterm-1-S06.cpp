#include <iostream>
using namespace std;
#define ll long long

ll myPow(ll x, int n) {
	ll res = 1;
	for (int i = 0; i < n; ++i) {
		res *= x;
	}
	return res;
}

int main() {
	ll n; int d = 0;
	cin >> n;
	ll t = n;
	while (t) {
		t /= 10;
		++d;
	}
	ll sum = 0;
	t = n;
	while (t) {
		int t2 = t % 10;
		t /= 10;
		sum += myPow(t2, d);
	}
	if (sum == n) {
		cout << "True";
	}
	else cout << "False";
}