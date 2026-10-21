#include <iostream>
#include <string>
#include <sstream>
#include <fstream>
#include <vector>

using namespace std;
struct Date {
	int day, month, year;
	string era; // AD or BC
};

struct General {
	string name, nationality;
	Date born, death;
	vector<string> known_battles;
};

struct Node {
	General general;
	Node* left;
	Node* right;
};

vector<General> prob1(string filename)
{

	ifstream mo;
	mo.open("file name");
	int n = 0;
	string line;
	getline(mo, line);
	while(!getline(mo, line))
	{
		n++;
	}

	General a[n];
	vector<General> gen;
	for (int i = 0; i < n; ++i) 
	{
		gen.push_back(a[i]);
	}
	if(!mo.is_open())
	{
		return gen;
	}
	mo.close();
	
	ifstream mo2("file name");
	if(mo2.is_open())
	{
		return gen;
	}
	getline(mo2, line);

	for (int i = 0; i < gen.size(); ++i) 
	{
		getline(mo2, line);
		stringstream ss(line);
		
		//ten
		getline(ss, gen[i].name, ',');
		//quoc tich
		getline(ss, gen[i].nationality, ',');
		//DD/MM/YYYY
		stringstream born(line);
		string token;
		getline(born, token, '-');
		gen[i].born.day = stoi(token);
		getline(born, token, '-');
		gen[i].born.month = stoi(token);
		getline(born, token);
		gen[i].born.year = stoi(token);
		getline(born, gen[i].born.era); 
		//mat
		stringstream mat(line);
		string temp;
		getline(mat, temp, '-');
		gen[i].death.day = stoi(temp);
		getline(mat, temp, '-');
		gen[i].death.month = stoi(temp);
		getline(mat, temp);
		gen[i].death.year = stoi(temp);
		getline(mat, gen[i].death.era); 
		//tran danh
		int batlle = 0;
		
	}
	return gen;
}


int main()
{
	
	return 0;
}
