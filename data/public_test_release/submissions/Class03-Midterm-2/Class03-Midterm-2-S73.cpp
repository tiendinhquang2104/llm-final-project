#include <iostream>

using namespace std;

void RemoveDuplicate(int arr[], int n)
{
    int Newn = 0;
    int Phantu = arr[0];
    for (int i = 1; i < n; i++) {
        while (i<n) {
            if (arr[i] != Phantu) {
                Newn++;
            } else {

            }

        }
    }
    for (int i = 0; i < Newn; i++) {
        cout << arr[i];
    }
}

/*int main()
{
    int n, arr[1000];
    cin >> n;
    for (int i = 0; i < n; i++) {
        cin >> arr[i];
    }
    RemoveDuplicate(arr,n);
       return 0;
}*/
