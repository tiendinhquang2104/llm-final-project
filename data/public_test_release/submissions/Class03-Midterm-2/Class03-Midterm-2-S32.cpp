#include <iostream>
using namespace std;

const int MAX = 10000;

//bool checkArray(int a[], int size) {
//	for (int )
//}

int main() {
	int a[MAX], size;
	cin >> size;
	for (int i = 0; i < size; i++) {
		cin >> a[i];
	}


	int b[MAX], new_size=0;
	bool check = 0;
	for (int i = 0; i < size-1; i++) {
		for (int j = i+1; j < size; j++) {
			if (a[i]==a[j]) {
				for (int z = i + 1; z < size; z++) {
					int temp = a[z];
					a
				}
		
			}

		}
		b[new_size] = a[i];
		new_size += 1;
	}


	cout << new_size << endl;
	for (int i = 0; i < new_size; i++) {
		cout << b[i] << " ";
	}



	return 0;
}