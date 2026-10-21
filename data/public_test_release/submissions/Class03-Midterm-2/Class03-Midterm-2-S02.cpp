#include <iostream>
using namespace std;

int main(){
	int n;
	cin >> n;
	int arr[10000];
	int checkArr[10000];
	for (int i = 0; i < n; i++) {
		cin >> arr[i];
	}
	for (int i = 0; i < 10000; i++) {
		checkArr[i] = 0;
	}

	for (int i = 0; i < n; i++) {
		if (checkArr[arr[i]] == 0) {
			cout << arr[i] << " ";
			checkArr[arr[i]] = 1;
		}
	}
	cout << endl;
	return 0;
}
