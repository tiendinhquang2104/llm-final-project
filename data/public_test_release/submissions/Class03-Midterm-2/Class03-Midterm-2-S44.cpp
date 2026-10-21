#include <iostream>
#include <fstream>

#define N 10000001

int a[10001], n;
bool posCheck[N], negCheck[N];

void init()
{
    std::cin >> n;
    for (int i = 0; i < n; i++)
    {
        std::cin >> a[i];
    }
    posCheck[0] = false;
    negCheck[0] = false;
}

void swap(int &a, int &b)
{
    int temp;
    temp = a;
    a = b;
    b = temp;
}

void result()
{
    std::cout << n << std::endl;
    for (int i = 0; i < n; i++)
    {
        std::cout << a[i] << " ";
    }
}

void check()
{
    int idxStand = 0;
    for (int i = 0; i < n; i++)
    {
        if ((a[i] >= 0 && posCheck[a[i]] == false) || (a[i] < 0 && negCheck[a[i]] == false))
        {
            if (a[i] >= 0)
                posCheck[a[i]] = true;
            else
                negCheck[a[i]] = true;
            swap(a[i], a[idxStand]);
            idxStand++;
        }
    }
    n = idxStand;
}

int main()
{
    init();
    check();
    result();
    return 0;
}