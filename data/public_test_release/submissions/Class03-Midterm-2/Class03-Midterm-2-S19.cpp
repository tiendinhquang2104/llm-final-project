#include <iostream>
using namespace std;

#define M 1000

void Input(int mang[], int &n)
{
    cin >> n;
    for (int i = 0; i < n; i++)
        cin >> mang[i];
}

bool CheckExist(int mang[], int n, int pos, int k)
{
    for (int i = 0; i < pos; i++)
    {
        if (mang[i] == k)
            return true;
    }
    return false;
}

int DeleteDuplicate(int mang[], int n)
{
    int j = 0;
    for (int i = 0; i < n; i++)
    {
        if (CheckExist(mang, n, i, mang[i]) == 1)
            continue;
        mang[j] = mang[i];
        j++;
    }
    return j;
}

void Output(int mang[], int n)
{
    cout << n << endl;
    for (int i = 0; i < n; i++)
        cout << mang[i] << " ";
}

int main()
{
    int n;
    int mang[M];
    Input(mang, n);
    int j = DeleteDuplicate(mang, n);
    Output(mang, j);
    return 0;
}