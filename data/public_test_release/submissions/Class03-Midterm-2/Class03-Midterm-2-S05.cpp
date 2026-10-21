#include <iostream>
using namespace std;

bool isEqual(int arr[], int stop, int element) {
	for (int i = 0; i <= stop; i++) {
		if (arr[i] == element) {
			return true;
		}
	}
	return false;
}

int main() {
	int a[1000];
	int arr[1000];

	int n;
	cin >> n;

	for (int i = 0; i < n; i++) {
		cin >> a[i];
	}

	int index = 0;
	arr[0] = a[0];
	for (int i = 0; i < n; i++) {
		if (!isEqual(arr, index, a[i])) {
			arr[++index] = a[i];
		}
	}
	cout << ++index << endl;
	for (int i = 0; i <= index; i++) {
		cout << arr[i] << " ";
	}

}