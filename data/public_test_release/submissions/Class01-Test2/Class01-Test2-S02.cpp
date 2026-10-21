#include <iostream>
#include <string>
#include <sstream>
#include <fstream>
#include <vector>

using namespace std;

struct Date {
	int day, month, year;
	string era;
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

Date parseDate(string& str) {
	Date d;
	stringstream ss(str);
	char dash1, dash2;
	ss >> d.day >> dash1 >> d.month >> dash2 >> d.year >> d.era;
	return d;
}

vector<string> parseBattles(string& str) {
	stringstream ss(str);
	string battle;
	vector<string> battles;
	while (getline(ss, battle, '|')) {
		battles.push_back(battle);
	}

	return battles;
}

vector<General> prob1(string filename) {
	fstream inFile(filename);
	string header;
	getline(inFile, header);

	vector<General> generals;
	string line;
	while (getline(inFile, line)) {
		stringstream ss(line);
		string nameStr, nationalityStr, bornStr, deathStr, knownBattlesStr;

		getline(ss, nameStr, ',');
		getline(ss, nationalityStr, ',');
		getline(ss, bornStr, ',');
		getline(ss, deathStr, ',');
		getline(ss, knownBattlesStr, ',');

		General gen;
		gen.name = nameStr;
		gen.nationality = nationalityStr;
		gen.born = parseDate(bornStr);
		gen.death = parseDate(deathStr);
		gen.known_battles = parseBattles(knownBattlesStr);

		generals.push_back(gen);
	}
	
	inFile.close();

	return generals;
}

Node* createNode(General x) {
	Node* newNode = new Node();
	newNode->general = x;
	newNode->left = nullptr;
	newNode->right = nullptr;
	return newNode;
}

bool isBornBefore(Date a, Date b) {
	if (a.era != b.era)
		return a.era == "BC";

	if (a.era == "BC") {
		if (a.year > b.year) return a.year > b.year;
		if (a.month < b.month) return a.month < b.month;
		if (a.day < b.day) return a.day < b.day;
	}
	else if (a.era == "AC") {
		if (a.year < b.year) return a.year < b.year;
		if (a.month < b.month) return a.month < b.month;
		if (a.day < b.day) return a.day < b.day;
	}

	return false;
}

void insertNode(Node*& pRoot, General x) {
	if (pRoot == nullptr) {
		pRoot = createNode(x);
		return;
	}

	if (isBornBefore(x.born, pRoot->general.born)) {
		insertNode(pRoot->left, x);
	}
	else if (isBornBefore(pRoot->general.born, x.born)) {
		insertNode(pRoot->right, x);
	}
}

Node* prob2(vector<General> generals) {
	Node* pRoot = nullptr;
	for (int i = 0; i < generals.size(); i++) {
		insertNode(pRoot, generals[i]);
	}

	return pRoot;
}

int prob3(Node* root, string born_year) {
	stringstream ss(born_year);
	string bornY, bornEra;
	getline(ss, bornY);
	getline(ss, bornEra);

	if (root == nullptr) return 0;
	else if ((root->general.born.year == stoi(bornY) && root->general.born.era == bornEra)) {
		return 1;
	}

	return prob3(root->left, born_year) + prob3(root->right, born_year);
}

/*void prob4(Node*& root, string battle){
	vector<General> blackList;
	
}*/

int main()
{
	Node* pRoot = nullptr;
	string filename = "50-best-european-generals-cleaned-first-20 (2).csv";
	vector<General> generals = prob1(filename);
	prob2(generals);
	cout << prob3(pRoot, "126 BC");
	return 0;
}

