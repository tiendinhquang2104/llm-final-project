#include <iostream> 
using namespace std;
int main() {
	int a[100];
	int n;
	cin >> n;
	for (int i = 0; i < n; i++) {
		cin >> a[i];
	}
	int count = 1;
	for (int i = 1; i < n; i++) {
		int j = 0;
		for (; j < count; j++) {
			if (a[i] == a[j]) break;
		}
		if (j == count ) {
			a[count++] = a[i];
		}
	}
	cout << count << endl;
	for (int i = 0; i < count; i++) {
		cout << a[i] << " ";
	}
	
	return 0;
}