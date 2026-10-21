#include <iostream>
#include <string>
using namespace std;

void sortAlpha(string arr[], int length);

int main() {
	string fullName;
	string first = "", second = "";
	bool is_name_turn = false;
	getline(cin, fullName);
	int len = fullName.size();
	for (int i = 0; i < len; i++) {
		if (fullName[i] != ' ') {
			if (is_name_turn) second += fullName[i];
			else first += fullName[i];
		}
		else is_name_turn = true;
	}
	int first_len = first.size();
	int second_len = second.size();
	string array[100];
	int n = 0;
	string res = "";
	for (int i = 0; i < first_len; i++) {
		res += first[i];
		string new_element = res;
		for (int j = 0; j < second_len; j++) {
			new_element += second[j];
			array[n] = new_element;
			n++;
		}
	}
	sortAlpha(array, n);
	cout << array[0];
	
	return 0;
}

void sortAlpha(string arr[], int length) {
	for (int i = 0; i < length - 1; i++) {
		int min = i;
		for (int j = i + 1; j < length; j++) {
			if (arr[min] > arr[j]) min = j;
		}
		if (min != i) {
			string tmp = arr[i];
			arr[i] = arr[min];
			arr[min] = tmp;
		}
	}
}

