#include <iostream>

using namespace std;

void Xuat(int b[], int& dem)
{
    cout << dem << endl;
    for( int i = 1; i <= dem; i++) {
        cout << b[i] << ' ';
    }
}

/*
void Sort(int a[], int& n)
{
    long long tam;
    for(int i = 1; i <= n; i++) {
        for( int j = 1; j <= n - i; j++) {
            if(a[j] > a[j+1]) {
                tam = a[j];
                a[j] = a[j+1];
                a[j+1] = tam;
            }
        }
    }
}
*/

void Solve(int& n, int D[], int DD[], long long f[], int& dem)
{
    for(int i = 1; i <= n; i++) {
        if(f[D[i]] == 0) {
            f[D[i]] = 1;
            dem++;
            DD[dem] = D[i];
        }
    }
}

int main()
{
    int n, dem=0;
    cin >> n;
    int D[n+1]={}, DD[n+1]={};
    long long f[100000]={};
    for(int i=1; i <= n; i++) {
        cin >> D[i];
    }
    Solve(n, D, DD, f, dem);
    Xuat(DD, dem);
}
