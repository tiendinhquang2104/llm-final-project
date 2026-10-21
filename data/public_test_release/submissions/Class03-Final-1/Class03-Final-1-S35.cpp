#include<iostream>
#include<cstring>
using namespace std;
int main() {
	char name[50];
	cin.getline(name, 50);
	int l = strlen(name);
	char ten[50];
	char ho[50];
	int vitri;
	for (int i = 0; i < l; i++) {
		if (name[i] == ' ') {
			vitri = i + 1;
			break;
		}
		else {
			ten[i] = name[i];
		}
	}
	for (int i = 0,vitri; vitri < l; i++, vitri++) {
		ho[i] = name[vitri];
	}




	return 0;
}