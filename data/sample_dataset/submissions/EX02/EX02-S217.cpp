#include <iostream>

using namespace std;

bool AmstrongNumber(unsigned int n)
{
    int sum = 0;
    int Luythua = 1;
    int count = 0
    int Sohang = 0;
    while (n>0) {
        Sohang = n%10;
        count++;
        n/=10;
    }

    for (int i = 1; i <= count; i++) {
        Luythua *= Sohang;
    }


    cout << sum;
    /*if (sum == n) {
        return true;
    } else
    {
        return false;
    }*/
}

int main ()
{
    unsigned int n;
    cin >> n;
    AmstrongNumber(n);
    int KQ = AmstrongNumber(n);
    /*if (KQ) {
        cout << "True";
    } else {
        cout << "False";
    }*/
}
