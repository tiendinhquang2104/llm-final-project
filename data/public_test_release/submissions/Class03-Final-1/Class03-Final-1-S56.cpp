#include<iostream>
#include<string>
using namespace std;
int main() {
	string ho,ten;
	cin >> ten;
	cin >> ho;
	string tong = "";
	string min1 = "zzzz";
	for (int i = 0; i < ten.size(); i++) {
		tong = tong + ten[i];
		string tmp = tong;
		for (int j = 0; j < ho.size(); j++) {
			tmp = tmp + ho[j];
			if (tmp < min1) {
				min1 = tmp;
			}

		}
	}
	cout << min1;
		return 0;
}