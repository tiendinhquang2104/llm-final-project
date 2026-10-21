#include <iostream>
#include <string>
#include <cstring>
#include <fstream>
#include <sstream>
using namespace std;

struct Date
{
	int day, month, year;
	string era;
};

struct General
{
	string name, nationality;
	Date born, death;
	int total_known_battles;
	string* known_battles;
};

struct Node {
	General general;
	Node* next;
};

General* prob1(string filename, int& n)
{
	ifstream fs;
	fs.open("filename");
	if(!fs.is_open())
	{
		cout << "Error";		
	}
	string line;
	getline(fs, line);
	
	while(getline(fs, line))
	{
		n++;
	}
	
	fs.close();
	
	ifstream fs2;
	fs2.open("filename");
	if(!fs2.is_open())
	{
		cout << "Error";
	}
	
	General* gen = new General[n];
	getline(fs, line);
	stringstream ss(line);
	int battle = 0;
	for(int i = 0; i < n; i++)
	{
		//ten
		getline(ss, gen[i].name, ',');
		
		//quoc tich
		getline(ss, gen[i].nationality, ',');
		
		//sinh
		getline(ss, line, '-');
		gen[i].born.day = stoi(line);
		gen[i].born.month = stoi(line);
		gen[i].born.year = stoi(line);
		getline(ss, gen[i].born.era, ',');
		
		//mat
		getline(ss, line, '-');
		gen[i].born.day = stoi(line);
		gen[i].born.month = stoi(line);
		gen[i].born.year = stoi(line);
		getline(ss, gen[i].born.era, ',');
		
		//so tran thang
		while(getline(ss, line, '|'))
		{
			battle++;
		}
		getline(ss, line, ',');
		gen[i].total_known_battles = battle;
		
		//bo infor thua
		getline(ss, line, ',');
		getline(ss, line, ',');
		getline(ss, line, ',');
		
		//known_battles
		getline(ss, *gen[i].known_battles);
	}
	fs.close();
	return gen;
}


Node* prob2(General* generals, int n)
{
		Node* a = new Node();
		a->next = NULL;

	
	return a;
}
int main()
{
	
	return 0;
}
