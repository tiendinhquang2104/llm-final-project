#include <iostream>
#include <string>


using namespace std;


void input(char a[]) {
	cout << "Nhap ten va ho: ";
	cin.getline(a,30);
}

void username(char a[], int n) {
	//char* p = &a[n];
	char c[10];
	int k = 1;
	c[0] = a[0];
	for (int i = 1; i < n; i++) {
		for (int j = 2; j < n; j++) {
			if ('a[i]' - 'a[j]' < 0) {
				c[k++] = a[i];
			}

			if (a[i] == ' ') {
				c[k++] = a[i + 1];
			}
		}
	}

	for (int j = 0; j < k; j++) {
		cout << c[j];
	}
}

int main() {
	char a[100];
	int n = strlen(a);
	input(a);
	username(a, n);
	return 0;
}