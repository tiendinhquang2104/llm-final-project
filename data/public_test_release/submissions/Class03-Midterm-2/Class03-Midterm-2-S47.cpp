#include <iostream>


using namespace std;

const int maxn = 10002;


int n, sz = 0, k = 0, first_arr[maxn], second_arr[maxn], tmp[maxn], b[maxn];

void docf(){

    cin >> n;
    for (int i = 1; i <= n; i++){
        cin >> first_arr[i];
        tmp[i] = first_arr[i];
    }

}


void xuli(){
    int id = 0;
    b[0] = tmp[0];
    for (int i = 1; i <= n; i++){
        bool fre = 0;
        for (int j = 0; j < id; j++){
            if (tmp[i] == b[j]){
                fre = true;
                break;
            }
        }
        if (fre) continue;
        b[id] = tmp[i];
        id++;
    }
    cout << id  << endl;
    for (int i = 0; i < id; i++) cout << b[i]<<" ";
}




int main(){

    docf();
    xuli();


    return 0;
}
