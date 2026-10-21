#include <iostream>

using namespace std;
long long mu(int n,int m){
      int n1 = n;
      for(int i = 1;i < m;i++)n*= n1;
      return n;
}
int dai(int n){
    int dem = 0;
    while(n > 0){
        dem++;
        n/= 10;
    }
    return dem;
}
void nhap(long long& n){
     cin >> n;
}
void armstrong(long long n,long long& tong){
    tong = 0;
    long long n1 = n;
    while(n > 0){
        int x = n%10;
        tong += mu(x,dai(n1));
        n/=10;
    }
}
void xuat(long long n,long long tong){
     if(tong == n)cout << "True";
     else cout << "False";
}
int main(){
    long long n,tong;
    nhap(n);
    armstrong(n,tong);
    xuat(n,tong);
   return 0;
}
