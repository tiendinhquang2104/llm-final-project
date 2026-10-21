#include <iostream>

using namespace std;

long long POW(int& a, int& b)
{
    int tam = 1;
    for(int i=1; i <= b; i++) {
        tam = tam * a;
    }
    return tam;
}

void MOD(int a, int D[], int& dem)
{
    while(a!=0)
    {
        D[dem]=a%10;
        a=a/10;
        dem++;
    }
    dem--;
}

void Solve(int& a, int D[], int& dem)
{
    long long b=0;
    for(int i=1; i <= dem; i++) {
        b = b + POW(D[i], dem);
    }
    if(b == a) cout << "True";
    else cout << "False";
}

int main()
{
    int n, dem=1;
    int D[11]={};
    cin >> n;
    MOD(n, D, dem);
    Solve(n, D, dem);
}
