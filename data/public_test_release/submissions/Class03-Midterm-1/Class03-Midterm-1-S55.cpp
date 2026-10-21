#include<iostream>

using namespace std;





int main() {

    long long numArr;
    cin >> numArr;
    int tmp = numArr;
    long long total = 0;
    int cnt = 0;
    while(numArr > 0) {
        ++cnt;
        numArr /= 10;
    }
    numArr = tmp;
    while(numArr > 0) {
        int cur = numArr % 10;
        int k = 1;
        for (int i = 1; i <= cnt; ++i) k *= cur;
        total += k;
        numArr /= 10;
    }
    if (total == tmp) cout << "True";
    else cout << "False";




    return 0;
}




