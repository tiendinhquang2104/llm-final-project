#include <iostream>
#include <bits/stdc++.h>
#define nmax 10009
#define N1max int(1e5) + 9
#define N2max int(1e5) + 9
using namespace std;

int main()
{

    bool check = 0, checkx = 0;
    int n, id(1), a[nmax] = {0};
    cin >> n;

    for (int i = 1; i <= n; i++){
        int x; cin >> x;
        for(int j = 1; j <= id; j++){
            if (a[j] == x && x != 0){

                check = 1;
                break;
            }
        }
        if (check == 1){
            check = 0;
            continue;
        }
        else{

                a[id++] = x;



        }
    }
    cout << --id << endl;
    for (int i = 1; i <= id; i++){
        cout << a[i] << " ";
    }
    return 0;
}

