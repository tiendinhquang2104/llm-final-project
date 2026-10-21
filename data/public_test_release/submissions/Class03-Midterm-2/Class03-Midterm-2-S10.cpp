#include <iostream>
using namespace std;
#define N 50

void Input(int arr[N], int &n)
{
	cin >> n;
	for (int i = 0; i < n; i++)
	{
		cin >> arr[i];
	}
}
void RemoveArr(int arr[N], int &n)
{
	int tmp = n;
	for (int i = 0; i < n; i++)
	{
		for (int j = i; j < tmp - 1; j++)
		{
			if (arr[j] == arr[j + 1])
			{
				for (int k = j; k < tmp - 1; k++)
				{
					arr[k] = arr[k + 1];
				}
			}
			j--;
			tmp--;
		}
	}
	for (int i = 0; i < tmp; i++)
	{
		cout << arr[i] << " ";
	}
}
int main()
{
	int arr[N], n;
	Input(arr, n);
	RemoveArr(arr, n);

	return 0;
}