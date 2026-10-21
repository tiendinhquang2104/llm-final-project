#include <iostream>
#include <fstream>
#include <string>

using namespace std;

string ho(string s) {
	string surname = "";
	int i = 0;
	while (s[i] != ' ') {
		surname += s[i];
		i++;
	}
	return surname;
}

string ten(string s) {
	string name = "";
	int i = 0;
	while (s[i] != ' ') i++;
	i++;
	while (i < s.length()) {
		name += s[i];
		i++;
	}
	return name;
}

string tienTo(string s) {
	string tienTo = "";
	tienTo += s[0];
	bool flag = true;
	for (int i = 0; i < s.length() / 2 - 1; i++) {
		if (!flag) break;
		for (int j = i + 1; j < s.length() / 2; j++) {
			if (s[i] >= s[j] && i != 0) {
				tienTo += s[j];
				continue;
			}
			else {
				flag = false;
				break;
			}
		}
	}
	return tienTo;
}

int main() {
	string s;
	getline(cin, s);
	string a = ho(s);
	string b = ten(s);
	cout << tienTo(a) << tienTo(b);
	return 0;
}