#include <iostream>

using namespace std;

int main()
{
    int a[100];
    int b[100];
    int n;
    int count = 0;
    cin >> n;
    bool flag = false;
    for (int i = 0; i < n; i++)
    {
        cin >> a[i];
    }
    int temp = a[0];
    for (int i = 0; i < n; i++)
    {

        for (int j = 0; j < n; j++)
        {

            if (a[j] == temp && flag == false)
            {
                flag = true;
                b[i] = temp;
                temp = a[j + 1];
                break;
            }

            if (a[j] != temp)
            {
                flag = false;
            }
            temp = a[j + 1];
        }
    }
    for (int i = 0; i < n; i++)
    {
        cout << b[i] << " ";
    }
}
