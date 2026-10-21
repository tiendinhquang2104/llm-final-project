#include <iostream>
#include<fstream>
#include<sstream>
#include<string>
#include<vector>
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
	vector<string> known_battles;
};
struct Node
{
	General general;
	Node* left;
	Node* right;
};
vector<General> prob1(string filename)
{
	vector<General> a;
	ifstream fin(filename);
	string line;
	getline(fin, line);
	while (getline(fin, line))
	{
		int i = 0;
		stringstream ss(line);
		string temp;
		getline(ss, a[i].name , ',');
		getline(ss, a[i].nationality, ',');
		getline(ss, temp, '-'); a[i].born.day = stoi(temp);
		getline(ss, temp, '-'); a[i].born.month = stoi(temp);
		getline(ss, temp, ' '); a[i].born.year = stoi(temp);
		getline(ss, a[i].born.era, ',');
		getline(ss, temp, '-'); a[i].death.day = stoi(temp);
		getline(ss, temp, '-'); a[i].death.month = stoi(temp);
		getline(ss, temp, ' '); a[i].death.year = stoi(temp);
		getline(ss, a[i].death.era, ',');
		getline(ss,a[i].known_battles[0], '|');
		getline(ss, a[i].known_battles[1], '|');
		getline(ss, a[i].known_battles[2], '|');
		getline(ss, a[i].known_battles[3], '|');
		getline(ss, a[i].known_battles[4], '|');
		i++;
	}
	return a;
}
Node* creatNode(General a)
{
	Node* temp = new Node;
	temp->general = a;
	temp->left = nullptr;
	temp->right = nullptr;
	return temp;
}
Node* prob2(vector<General> general)
{
	Node* root = new Node;
	for (int i = 0; i < general.size()-1; i++)
	{
		for (int j = i + 1; j < general.size(); i++)
		{
			if (general[i].born.year < general[j].born.year|| general[i].born.month < general[j].born.month || general[i].born.day < general[j].born.day  )
			{
				root->left = creatNode(general[i]);
			}
			else if (general[i].born.year < general[j].born.year || general[i].born.month < general[j].born.month || general[i].born.day < general[j].born.day)
			{
				root->right = creatNode(general[i]);
			}
		}
	}
	return root;
}
int main()
{


	return 0;
}