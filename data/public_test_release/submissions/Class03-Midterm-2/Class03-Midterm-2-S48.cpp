#include <iostream>
using namespace std;

int main() {

	int n;
	int arr[50];
	int k = 0;

	cin >> n;

	for (int i = 0; i < n; i++)
		cin >> arr[i];


	int res[50];
	for (int i = 0; i < n; i++) {
		if (arr[i] == arr[i + 1]) {
			res[k++] = arr[i + 1];
		}
	}


	cout << k << endl;

	for (int i = 0; i < k; i++)
		cout << res[i] << " ";



	return 0;
}
