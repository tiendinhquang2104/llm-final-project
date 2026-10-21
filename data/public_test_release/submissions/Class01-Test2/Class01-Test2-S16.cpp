#include<iostream>
#include<string>
#include<fstream>
#include<sstream>
#include<vector>
//Address: R"(C:\Users\sv\Documents\50-best-european-generals-cleaned-first-20 (1).csv)"
using namespace std;
struct Date {
	int day, month, year;
	std::string era;
};
struct General {
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
Date Split(string buffer)
{
	Date a;
	std::stringstream ss(buffer);
	std::string line = " ";
	while (getline(ss, line, '-'))
	{
		a.day = stoi(line);
		getline(ss, line, '-');
		a.month = stoi(line);
		getline(ss, line, ' ');
		a.year = stoi(line);
		getline(ss, line);
		a.era = line;
	}
	return a;
}
vector<string> know_battles(string buffer)
{
	std::stringstream ss(buffer);
	std::string temp;
	vector<string> a;
	while (getline(ss, temp, '|'))
	{
		a.push_back(temp);
	}
	return a;
}
vector <General> prob1(string filename)
{
	vector<General> arr;
	std::ifstream fin(filename);
	std::string buffer = "";
	getline(fin, buffer, '\n');
	General a;
	vector<string> known;
	if (fin.is_open())
	{
		while (getline(fin, buffer, ','))
		{
			a.name = buffer;
			getline(fin, buffer, ',');
			a.nationality = buffer;
			getline(fin, buffer, ',');
			Date birth = Split(buffer);
			a.born = birth;
			getline(fin, buffer, ',');
			Date death = Split(buffer);
			a.death = death;
			getline(fin, buffer, ',');
			vector<string> temp_battles = know_battles(buffer);
			a.known_battles = temp_battles;
			getline(fin, buffer, '\n');
			arr.push_back(a);
		}
		fin.close();
	}
	else
	{
		std::cout << "Cannot open this file" << "\n";
	}
	return arr;
}
Node* CreateNode(General&a)
{
	Node* newnode = new Node;
	newnode->general = a;
	newnode->left = nullptr;
	newnode->right = nullptr;
	return newnode;
}
void InsertNode(Node*&root, General a)
{
	if (root == nullptr)
	{
		root = CreateNode(a);
		return;
	}
	else if (root->general.born.year > a.born.year)
	{
		InsertNode(root->left, a);
	}
	else if (root->general.born.year == a.born.year)
	{
		if (root->general.death.year > a.death.year)
		{
			InsertNode(root->left, a);
		}
		else
		{
			InsertNode(root->right, a);
		}
	}
	else
	{
		InsertNode(root->right, a);
	}
}
Node* prob2(vector<General>&generals)
{
	Node* root = nullptr;
	for (int i = 0; i < generals.size(); i++)
	{
		InsertNode(root, generals[i]);
	}
	return root;
}
int SplitForString(string buffer)
{
	std::stringstream ss(buffer);
	std::string byear;
	int year = 0;
	while (getline(ss, byear, ' '))
	{
		year = stoi(byear);
	}
	return year;
}
string SplitFromString(string buffer)
{
	std::stringstream ss(buffer);
	std::string byear;
	std::string era;
	int year = 0;
	while (getline(ss, byear, ' '))
	{
		year = stoi(byear);
		getline(ss, era);
	}
	return era;
}
int prob3(Node* root, string born_year)
{
	if (root == nullptr) return 0;
	int source_year = SplitForString(born_year);
	std::string eofgeneral = SplitFromString(born_year);
	int temp_year = root->general.born.year;
	std::string temp_era = root->general.born.era;
	return (temp_year == source_year && eofgeneral == temp_era) + prob3(root->left, born_year) + prob3(root->right, born_year);
}

