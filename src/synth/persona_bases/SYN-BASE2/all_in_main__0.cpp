#include <iostream>
#include <string>
using namespace std;

int main()
{
    long long n;
    cin >> n;
    string kq = "";
    do
    {
        if (n % 2 == 1)
            kq = "1" + kq;
        else
            kq = "0" + kq;
        n = n / 2;
    } while (n > 0);
    cout << kq;
    return 0;
}
