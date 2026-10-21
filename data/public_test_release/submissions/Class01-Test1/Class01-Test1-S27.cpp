#include<iostream>
#include<sstream>
#include<string>
#include<cstring>
#include<fstream>
using namespace std;


struct Date {
	int day, month, year;
	string era; 
};
struct General {
	string name, nationality;
	Date born, death;
	int total_known_battles;
	string* known_battles;
};
struct Node {
	General general;
	Node* next;
};
int countline(string filename)
{
	int count = 0;
	string line;
	ifstream fin(filename);
	if (!fin.is_open()) return 0;
	getline(fin, line);
	while (getline(fin, line))
	{
		if (!line.empty()) count++;
	}
	fin.close();
	return count;
}
int mystoi(string s)
{
	if (s == "") return 0;
	return stoi(s);
}

General* prob1(string filename, int& n)
{
	string line;
	stringstream fin(filename);
	General* a = new General;
	getline(fin, line);
	while (getline(fin, line))
	{
		getline(fin, a->name, ',');
		getline(fin, a->nationality, ',');
		getline(fin, line, '-'); a->born.day = mystoi(line);
		getline(fin, line, '-'); a->born.month = mystoi(line);
		getline(fin, line, ' '); a->born.year = mystoi(line);
		getline(fin, a->born.era, ',');
		getline(fin, line, '-'); a->death.day = mystoi(line);
		getline(fin, line, '-'); a->death.month = mystoi(line);
		getline(fin, line, ' '); a->death.year = mystoi(line);
		getline(fin, a->death.era, ',');
		getline(fin, a->known_battles[0], '|');
		getline(fin, a->known_battles[1], '|');
		getline(fin, a->known_battles[2], ',');
		getline(fin, line, ',');
		getline(fin, line, ',');
		getline(fin, line, ',');
		line.clear();
		getline(fin, line, ','); a->total_known_battles = mystoi(line);
	}
	return a;
}










Node* creatnode(General a)
{
	Node* temp = new Node;
	temp->general = a;
	temp->next = nullptr;
	return temp;
}














int main()
{
	return 0;
}