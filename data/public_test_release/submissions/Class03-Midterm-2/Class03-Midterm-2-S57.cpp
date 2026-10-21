#include <iostream>
using namespace std;
int main() {
	int n;
	int A[10000];
	cin >> n;
	for (int i = 0; i < n; i++) {
		cin >> A[i];
	}
	int temp;
	for (int i = 0; i < n; i++) {
		for(int j = i; j < n; j++) {
			if (A[i] > A[j]) {
				temp = A[i];
				A[i] = A[j];
				A[j] = temp;
			}
		}
	}
	bool fl=false;
	int temp2;
	for (int i = 0; i < n; i++) {
		if (!fl) {
			temp2 = A[i];
				fl = true;
		}
		else {
			if (A[i] == temp2) {
				for (int j = i; j < n; j++) {
					A[j] = A[j + 1];
				}
				i--;
				n--;
			}
			else { 
				
				fl = false; 
				i--;
			}
		}
	}
	cout << n<<endl;
	for (int i = 0; i < n; i++) {
		cout << A[i] << " ";
	}
}