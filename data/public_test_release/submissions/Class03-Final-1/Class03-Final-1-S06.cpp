#include <iostream>
#include <string>

using namespace std;

int main() {
	string s1, s2;
	cin >> s1 >> s2;
	string minString = "";
	minString += s1[0];
	minString += s2[0];
	for (int j = 0; j < s2.length(); ++j) {
		string postfix = s2.substr(0, j + 1);
		string curMinString = s1 + postfix;
		for (int i = 0; i < s1.length(); ++i) {
			string prefix = s1.substr(0, i + 1);
			string curString = prefix + postfix;
			if (curString < curMinString) curMinString = curString;
		}
		if (curMinString < minString) minString = curMinString;
	}
	cout << minString;

	/*string s1, s2;
	cin >> s1 >> s2;
	char postfix = s2[0];
	string minString = "";
	minString += s1[0];
	minString += postfix;

	string curString = "";
	curString += s1[0];
	for (int i = 1; i < s1.length(); ++i) {
		if (curString + s1[i] + postfix < minString) {
			minString = curString + s1[i] + postfix;
			curString += s1[i];
		}
		else break;
	}
	cout << minString;*/

	/*string s1, s2;
	cin >> s1 >> s2;
	string minString = "";
	minString += s1[0];
	char postfix = s2[0];
	for (int i = 1; i < s1.length(); ++i) {
		if (s1[i] < postfix) minString += s1[i];
		else break;
	}
	cout << minString + postfix;*/
}
