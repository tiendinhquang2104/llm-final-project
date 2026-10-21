#include<iostream>

using namespace std;

const int MAXN = 1e4 + 5;


int arr[MAXN], res[MAXN];
int numArr;



int main() {

    cin >> numArr;
    for (int i = 1; i <= numArr; ++i) cin >> arr[i];
    int cnt = 0;
    for (int i = 1; i <= numArr; ++i) {
        int check = 1;
        for (int j = i - 1; j > 0; --j) {
            if (arr[i] == arr[j]) {
                check = 0;
                break;
            }
        }
        if (check) res[++cnt] = arr[i];
    }
    cout << cnt << '\n';
    for (int i = 1; i <= cnt; ++i) cout << res[i] << " ";







    return 0;
}




