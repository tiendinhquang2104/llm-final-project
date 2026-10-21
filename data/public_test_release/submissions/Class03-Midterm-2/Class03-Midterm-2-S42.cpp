#include <iostream>
using namespace std;






int arr[10000];
int numdiff[10000];

int main() {
	int n; //size array
	cin >> n;

	int count;


	for (int i = 1; i <= n; i++)
	{
		cin >> arr[i];
	}

	int cnt = 0;

	for (int i = 1; i <= n; i++)
	{
		count = 1;
		for (int j = i - 1; j > 0; j--)
		{
			if (arr[j] == arr[i])
			{
				count = 0;
				break;
			}
		}

		if (count)
		{
			numdiff[++cnt] = arr[i];
		}
	}

	cout << cnt << endl;
	for (int i = 1; i <= cnt; i++)
	{
		cout << numdiff[i] << " ";
	}




	return 0;
}