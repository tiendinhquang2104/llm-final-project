#include <iostream>
#include <iomanip>
#include <cmath>

using namespace std;

long long a[10], n, k, sum = 0;

void docf(){
    cin >> n;
    k = n;
}

long long tinh_so_mu(int m, int gt){

    long long res = gt;
    for (int i = 1; i < m; i++) res *= gt;
    return res;

}

void process(){
    int tong_chu_so = 0;
    while(n){
        tong_chu_so++;
        a[tong_chu_so] = n % 10;
        n /= 10;

    }
    //cout << tong_chu_so << endl;

    for (int i = 1; i <= tong_chu_so; i++){

        sum += tinh_so_mu(tong_chu_so, a[i]);

    }
    //cout << sum << endl;

}

bool Test(long long First_gt, long long Second_gt){
    return (First_gt == Second_gt);
}

void Xuat(){

    if (Test(k, sum)) cout << "True";
    else cout << "False";

}
int main(){

    docf();

    process();

    Xuat();

    return 0;
}
