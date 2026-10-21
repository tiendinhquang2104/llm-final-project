#include <iostream>
#include <string>
using namespace std;
int main() {
	string name;
	string kq = "";
	getline(cin, name);
	string sub = name.substr(0, name.find(' '));
	if (sub.length() <= 3) {
		kq += sub; 
	}
	else {
		kq += sub[0];
		kq += sub[1];
	}
	name.erase(0, name.find(' ') + 1);
	kq += name[0];
	cout << kq;

	return 0;
}