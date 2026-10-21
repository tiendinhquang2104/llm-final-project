#include <iostream>

using namespace std;

void input(int &n, int arr[])
{
    cin >> n;
    for (int i = 0; i < n; i++)
    {
        cin >> arr[i];
    }
}
void removeDuplicates(int n, int arr[], int a[], int &cnt)
{
    bool check = false;
    a[0] = arr[0];
    for (int i = 0; i < n; i++)
    {
        for (int j = 0; j < cnt; j++)
        {
            if (arr[i] == a[j])
            {
                check = false;
                break;
            }
            else if (j == cnt - 1)
            {
                check = true;
                break;
            }
        }
        if (check)
            a[cnt++] = arr[i];
    }
}

void output(int cnt, int a[])
{
    cout << cnt << endl;
    for (int i = 0; i < cnt; i++)
    {
        cout << a[i] << " ";
    }
}

int main()
{
    int n;
    int cnt = 1;
    int arr[10000];
    int a[10000];
    input(n, arr);
    removeDuplicates(n, arr, a, cnt);
    output(cnt, a);
    return 0;
}