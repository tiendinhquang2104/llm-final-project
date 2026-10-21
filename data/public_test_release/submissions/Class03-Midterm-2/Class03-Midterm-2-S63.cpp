#include <iostream>
using namespace std;

#define MAX 10000
int frequency[MAX] = {0};
int n, number = 0;

int main()
{
    cin >> n;
    if ((n < 1) && (n > 10000))
    {
        cout << "Vuou qua gioi han, moi ban nhap lai";
        cin >> n;
    }

    for (int i = 0; i < n; i++)
    {
        cin >> number;
        frequency[number]++;
    }
    int b[MAX] = {0};
    int j = 0;
    for (int i = 0; i < MAX; i++)
    {
        if (frequency[i] >= 1)
        {
            b[j] = i;
            j++;
        }
    }
    cout << j - 1 << endl;
    for (int i = 0; i < j; i++)
    {
        cout << b[i] << " ";
    }
}
