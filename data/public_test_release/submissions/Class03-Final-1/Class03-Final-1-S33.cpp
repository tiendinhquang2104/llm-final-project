#include <iostream>
#include <string>
using namespace std;

int main() {
	string hoten;
	getline(cin, hoten);
	
	int n = hoten.length();
	
	char temp = 'a';
	for (int i = 0; i < n; i++) {
		if (hoten[i] == ' ') temp = hoten[i + 1];
	}
	cout << hoten[0];

	for (int i = 1; i < n; i++) {
		if (hoten[i] <= temp) {
			if (hoten[i] != ' ') cout << hoten[i];
			if (hoten[i] == ' ') break;
		}

	}
	cout << temp;

















	return 0;
}