#include<iostream>
using namespace std;
void input(int &n, int a[]) {
	cin >> n;
	for (int i = 0; i < n; i++) cin >> a[i];
}
bool first_seen(int n, int value, int a[]) {
	for (int i = 0; i < n; i++) {
		if (a[i] == value) return false;
	}
	return true;
}

void unordered_Set(int& n, int a[]) {
	int cnt = 1;
	int tem[10000];
	tem[0] = a[0];
	for (int i = 1; i < n; i++) {
		if (first_seen(n, a[i], tem)) {
			cnt++;
			tem[cnt - 1] = a[i];
		}
	}
	for (int i = 0; i < cnt; i++) a[i] = tem[i];
	n = cnt;
}
void output(int n, int a[]) {
	cout << n << endl;
	for (int i = 0; i < n; i++) cout << a[i] << " ";
}
int main() {
	int n;
	int a[10000];
	input(n, a);
	unordered_Set(n, a);
	output(n, a);
}