#include <iostream>

using namespace std;

void Sort(int n,long long a[]){
    for(int i = 0;i < n-1;i++){
        for(int j = i+1;j < n;j++){
            if(a[i] < a[j]){
                int temp = a[i];
                a[i] = a[j];
                a[j] = temp;
            }
        }
    }
}
int sokhac(int n,long long b[]){
    int dem = 1;
    for(int i = 0;i < n-1;i++){
        if(b[i] != b[i+1])dem++;
    }
    return dem;
}
void doc(int n,long long a[],long long c[]){
    int dem = 0;
    for(int i = 0;i < n;i++){
        int dem1 = 0;
        for(int j = i-1;j >= 0;j--){
            if(a[i] == a[j])c[i]++;
        }
    }
}
void nhap(int& n,long long a[],long long b[]){
    cin >> n;
    for(int i = 0;i < n;i++){
        cin >> a[i];
        b[i] = a[i];
    }
}
void xuat(int n,long long a[],long long b[],long long c[]){
     cout << sokhac(n,b) << endl;
     for(int i = 0;i < n;i++){
        if(c[i] == 0)cout << a[i] << " ";
     }
}
int main(){
    int n;
    long long a[10000],b[10000],c[10000];
    nhap(n,a,b);
    Sort(n,b);
    doc(n,a,c);
    xuat(n,a,b,c);
   return 0;
}
