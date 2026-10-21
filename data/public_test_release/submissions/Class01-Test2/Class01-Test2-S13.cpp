#include <iostream>
#include <fstream>
#include <sstream>
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

Date readDate(const string& s) {
	stringstream ss(s);
	string tmp;
	Date d;

	getline(ss, tmp, '-');
	d.day = stoi(tmp);

	getline(ss, tmp, '-');
	d.month = stoi(tmp);

	getline(ss, tmp, ' ');
	d.year = stoi(tmp);

	getline(ss, d.era);

	return d;
}

vector<string>splitbattles(const string& s, int& cnt) {
	stringstream ss(s);
	string temp; 
	vector<string>tmp;

	while (getline(ss, temp, '|')) {
		tmp.push_back(temp);
	}

	cnt = tmp.size();
	vector<string> a;

	for (int i = 0; i < cnt; i++) {
		a.push_back(tmp[i]);
	}

	return a;
}

vector<General> prob1(string filename) {
	vector<General>list;
	ifstream fin(filename);

	if (fin.is_open()) return list;

	string line;

	getline(fin, line);

	while (getline(fin, line)) {
		stringstream ss(line);
		string tmp;
		General g;

		getline(ss, g.name, ',');

		getline(ss, g.nationality, ',');

		getline(ss, tmp, ',');
		g.born = readDate(tmp);

		getline(ss, tmp, ',');
		g.death = readDate(tmp);

		getline(ss, tmp, ',');
		int cnt;
		g.known_battles = splitbattles(tmp, cnt);

		getline(ss, tmp, ',');

		getline(ss, tmp, ',');

		getline(ss, tmp, ',');

		getline(ss, tmp, ',');

		
	}

	fin.close();
	return list;
}

struct Node {
	General general;
	Node* left;
	Node* right;
};

int ConvertYear(Date d) {
	if (d.era == "BC") return -d.year;

	return d.year;
}

int readYear(Date a, Date b) {
	int ya = ConvertYear(a);
	int yb = ConvertYear(b);

	if (ya != yb) return ya - yb;

	if (a.month != b.month) return a.month - b.month;

	return a.day - b.day;
}

Node* prob2(vector<General> generals) {
	Node* p = new Node;
	p->general = generals;
	p->left = p->right = nullptr;
	return p;
}

Node* InsertBST(Node*& root, vector<General> g) {
	if (!root) {
		root = prob2(g);
		return root;
	}

	if (readYear(g.born, root->general.born) < 0) return InsertBST(root->left, g);

	else if (readYear(g.born, root->general.born) > 0) return InsertBST(root->right, g);

	return root;
}

int prob3(Node* root, string born_year) {
	if (!root) return 0;

	int cnt = 0;
	if (root->general.born.year == born_year) return 1;

	return cnt + prob3(root->left, born_year) + prob3(root->right, born_year);
}

Node* Findmin(Node* root) {
	while (root->left) {
		root = root->left;
	}
	return root;
}

void prob4(Node*& root, string battle) {
	if (!root) return;
	if (battle != root->general.known_battles) {
		if (!root->left && !root->right) {
			delete root;
			root = nullptr;
		}

		else if (!root->left) {
			Node* p = root;
			root = root->right;
			delete p;
		}

		else if (!root->right) {
			Node* p = root;
			root = root->left;
			delete p;
		}

		else {
			Node* p = Findmin(root->right);
			root->general = p->general;
			prob4(root->right, p->general.known_battles);
		}
	}
	else {
		prob4(root->left, battle);
		prob4(root->right, battle);
	}
}