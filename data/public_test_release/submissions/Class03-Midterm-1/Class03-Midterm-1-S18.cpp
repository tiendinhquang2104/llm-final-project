#include <iostream>
using namespace std;

//Ham mu
long long mu (long long x, long long y){
    long long tmp = x;
    for (int i = 1; i < y; i++) x*= tmp;
    return x;
}

int main(){
    long long n;
    cin >> n;
    long long chuso[20];
    int scs = 0;
    long long tmp = n;
    int all1 = 1, is0 = 1;

    //Lay tung chu so cua n
    while (tmp != 0){
        is0 = 0;
        chuso[scs] = tmp % 10;
        if (tmp % 10 > 1 && n!= 1) all1 = 0;
        tmp /= 10;
        scs++;
    }
    int i = 1, j = 1;
    long long sum = -1;
    int kq = 0;

    //Thu cac so mu
    while (sum < n && !all1){
        sum = 0;
        for (int i = 0; i < scs; i++){
            sum += mu(chuso[i], j);
        }
        j++;
        if (sum == n){
            kq = 1;
            break;
        }
    }
    if (is0) kq = 1;
    if (kq) cout << "True";
    else cout << "False";
}
