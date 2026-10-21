#include <iostream>

#define maxN 10005
#define oo (int)(2e9)

using namespace std;

int n;
int b[maxN], a[maxN];

int main() {
	cin >> n;

    for (int i = 1; i <= n; ++i) {
        cin >> a[i];
        b[i] = a[i];
    }

    for (int i = 1; i <= n-1; ++i) {
        for (int j = i+1; j <= n; ++j) {
            if (a[i] == a[j]) a[j] = 0;
        }
    }

    int m = 0;

    for (int i = 1; i <= n; ++i) {
        if (a[i] != 0) ++m;
        if (b[i] == 0 && a[i] == 0) ++m;
    }

    cout << m << "\n";

    for (int i = 1; i <= n; ++i) {
        if (a[i] != 0) cout << b[i] << " ";
        if (b[i] == 0 && a[i] == 0) cout << b[i] << " ";
    }

    cout << "\n";

	return 0;
}
