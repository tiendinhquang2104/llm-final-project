#include <iostream>
#include <string>
using namespace std;
int main() {
	string Name = "";
	string Familyname = "";
	string s;
	string tong = "";
	string Min = "zzzzzz";
	getline(cin, s);
	int i = 0;
	bool metSpace = false;
	while (i < s.length()) {
		if (!metSpace && s[i] != ' ') {
			Name += s[i];
		}
		if (s[i] == ' ')
			metSpace = true;
		if (metSpace && s[i] != ' ')
			Familyname += s[i];
	}
	string result = "";
	for (int i = 0; i < Name.length(); i++) {
		tong = tong + Name[i];
		string tmp = tong;
		for (int j = 0; j < Familyname.length(); j++) {
			tmp = tmp + Familyname[j];
			if (tmp < Min) Min = tmp;
		}
	}
	cout << Min;
}