#include <iostream>
#include <string>
using namespace std;


int main() {

	string h, t;
	cin >> h >> t;
	int n = h.size();
	int m = t.size();
	int i = 0,j = 0;
	string kq;
	while (i == 0 || j == 0) {
		if (i<n&& (h[i]<t[j] || i==0)) {
			kq += h[i];
			i++;
		}
		else if(j<m &&h[i]>=t[j] ) {
			kq += t[j];
			j++;
		}

	}
	cout << kq;


	return 0;

}