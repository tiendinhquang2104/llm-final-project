#include<iostream>
#include<string>
#include<cstring>

using namespace std;

string find_tien_to(string s, int n) {
	string res = "";
	for (int i = 0; i < n; i++) {
		res += s[i];
	}
	return res;
}

void cut_line(string& s1, string& s2, string str) {
	int i = 0;
	for (i; i < str.size(); i++) {
		if (str[i] == ' ') break;
		s1 += str[i];
	}
	for (int j = i + 1; j < str.size(); j++) {
		s2 += str[j];
	}
}
int cut_line_pos(string str) {
	int idx = 0;
	while (idx < str.size()) {
		if (str[idx] == ' ') break;
		idx++;
	}
	return idx;
}

void login_name(string s) {
	string s1, s2;
	int pos = cut_line_pos(s);
	cut_line(s1, s2, s);
	string res = s1 + s2;
	int size1 = s1.length();
	int size2 = s2.length();
	for (int i = 0; i < size1; i++) {
		string tien_to_s1 = find_tien_to(s1, i + 1);
		for (int j = 0; j < size2; j++) {
			string tien_to_s2 = find_tien_to(s2, j + 1);
			string tmp = tien_to_s1 + tien_to_s2;
			if (tmp < res) res = tmp;
		}
	}
	cout << res;
}


int main() {
	string s;
	cin >> s;
	string s1, s2;
	//int pos =  cut_line_pos(s);
	//s1 = s.substr(0, pos + 1);
	//s2 = s.substr(pos , s.size() - pos - 1);
	//cout << s1 << endl;
	// << s2 << endl;
	login_name(s);
	return 0;
}