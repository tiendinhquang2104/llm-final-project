#include <iostream>
#include<string>
#include<fstream>
#include<sstream>
using namespace std;
struct Battle {
	string name, location;
	string from_date, to_date;
	int total_famous_generals;
	string* list_famous_generals;
};
struct Node {
	Battle battle;
	Node* next;
};
// dem
int countline(const string& filename) {
	int dem = 0;
	string line;
	ifstream file(filename);
	getline(file, line);
	while (getline(file, line)) {
		dem++;
	}
	file.close();
	return dem;
}
// check
int check(const string& line) {
	if (line.empty())
		return 0;
	return stoi(line);
}
// pro 1
Battle* pro1(string filename, int& n) {
	n = countline(filename);
	string line;
	string temp;
	ifstream file(filename);
	int i = 0;
	getline(file, line);
	Battle* ketqua = new Battle[n];
	while (getline(file, line) && i < n) {
		stringstream ss(line);
		getline(ss, ketqua[i].name, ',');
		getline(ss, ketqua[i].location, ',');
		getline(ss, ketqua[i].from_date, ',');
		getline(ss, ketqua[i].to_date, ',');
		getline(ss, temp, ',');
		ketqua[i].total_famous_generals = check(temp);
		i++;
	};
	file.close();
	return ketqua;
};
// pro2
// pro 3


int main()
{
	int n;
	Battle* pro = pro1("D:\\50-european-battles-first-20.csv", n); {
		if (pro != nullptr && n > 0) {
			cout << pro[0].name;
		}
	};


		
}


