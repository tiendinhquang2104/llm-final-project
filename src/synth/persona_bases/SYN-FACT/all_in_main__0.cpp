#include <iostream>
using namespace std;

int main()
{
    int n;
    cin >> n;
    long long gt = 1;
    for (int i = n; i > 1; i--)
        gt *= i;
    cout << gt << endl;
    return 0;
}
