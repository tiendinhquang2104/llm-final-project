//A B C D E F G H I J K L M N O P Q R S T U V W S Y Z

#include <string>
#include <iostream>

using namespace std;

string toLower(string& s) {
	for (int i = 0; i < s.size(); i++) {
		s[i] = tolower(s[i]);
	}
	return s;
}

string exercise_1(const string& ten, const string& ho) {
	string tenDangNhap = "";
	int i = 0, j = 0;
	while (i <= ten.size() && j <= ho.size()) {
		if (ten[i] <= ho[j]) {
			tenDangNhap = tenDangNhap + ten[i];
		}
		else {
			tenDangNhap = tenDangNhap + ho[j];
			return tenDangNhap;
		}
		i++;
		j++;
	}
	return tenDangNhap;
}
//harry potter

int main() {
	string ten, ho;
	cin >> ten;
	cin >> ho;
	ten = toLower(ten);
	ho = toLower(ho);

	string tenDangNhap = exercise_1(ten, ho);
	cout << tenDangNhap;
	return 0;


}