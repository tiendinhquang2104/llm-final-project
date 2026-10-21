#include <iostream>
using namespace std;


int main(){
    int n;
    cin >> n;
    int a[n + 1];
    for (int i = 0; i < n ; i++) cin >> a[i];
    int kq[n + 1];
    int dem = 0;

    //Ktra phan tu trong mang a co trung mang kq khong
    for (int i = 0 ; i < n; i ++){
        int kt = 0;
        for (int j = 0; j < dem; j++){
            if (a[i] == kq[j]) {
                kt = 1;
                break;
            }
        }
        if (!kt){
            kq[dem] = a[i];
            dem ++;
        }
    }
    cout << dem << endl;
    for (int i = 0; i < dem; i++) cout << kq[i] << " ";
    return 0;
}
