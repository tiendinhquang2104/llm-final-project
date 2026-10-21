#include <iostream>
#include <string>
using namespace std;



int main()
{
	string ho, ten;
	cin >> ho >> ten;
	int hosize = ho.size();
	ho = " " + ho;
	int tensize = ten.size();

	char pivot = ten[0];
	int tmp = pivot - 'a';
	string res = "";
	res += ho[1];

	for (int i = 2; i <= hosize; i++)
	{
		int curl = ho[i] - 'a';
		if (curl >= tmp) break;
		res = res + ho[i];
			
	}
	res += pivot;
	cout << res;




	return 0;
}
