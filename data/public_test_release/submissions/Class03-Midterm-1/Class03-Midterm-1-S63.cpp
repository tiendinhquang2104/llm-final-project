#include <iostream>

using namespace std;

long long Pow(int n, int k)
{
    int origin = n;
    for (int i = 1; i < k; i++)
        n *= origin;

    return n;
}
bool check(int n)
{
    int origin = n;
    int id(0), a[20] = {0};
    long long ans(0);
    while(n != 0){
        id++;
        a[id] = n%10;
        n /= 10;

    }
    for (int i = 1; i <= id; i++){
        ans += Pow(a[i],id);
    }
    if (ans == origin)
        cout << "True";
    else
        cout << "False";
}

int main()
{
    int n; cin >> n;
    check(n);
    return 0;
}
