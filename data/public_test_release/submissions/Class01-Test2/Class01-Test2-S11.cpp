
#include <iostream>
#include <string>
#include <sstream>
#include <vector>
#include <fstream>
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
//prob1----------------------------
vector<General> prob1(string filename) {
	vector<General> v;
	ifstream file(filename);
	if (!file) return v;

	string line;
	getline(file, line);
	int i = 0;
	while (getline(file, line)) {
		if (line == "") continue;
		stringstream ss(line);
		string temp;
		getline(ss, v[i].name, ',');
		getline(ss, v[i].nationality, ',');
		getline(ss, temp, '-');
		v[i].born.day = stoi(temp);
		getline(ss, temp, '-');
		v[i].born.month = stoi(temp);
		getline(ss, temp, ' ');
		v[i].born.year = stoi(temp);
		getline(ss, v[i].born.era, ',');
		getline(ss, temp, '-');
		v[i].born.day = stoi(temp);
		getline(ss, temp, '-');
		v[i].born.month = stoi(temp);
		getline(ss, temp, ' ');
		v[i].born.year = stoi(temp);
		getline(ss, v[i].born.era, ',');
		getline(ss, temp, ',');
		stringstream ss2(temp);
		while (getline(ss2, temp, '|')) v[i].known_battles.push_back(temp);
		getline(ss, temp, ',');
		getline(ss, temp, ',');
		getline(ss, temp, ',');
		getline(ss, temp, ',');
		++i;
	}
	file.close();
	return v;
}
struct Node {
	General general;
	Node* left;
	Node* right;
};
//prob2----------------------------
Node* makeNode(General x) {
	Node* newNode = new Node;
	newNode->general = x;
	newNode->left = newNode->right = NULL;
	return newNode;
}
bool sosanhborn(General x, General y) {
	if (x.born.era == "BC" && y.born.era == "AD") return true;
	else if (x.born.era == "AD" && y.born.era == "BC") return false;
	else if (x.born.year != y.born.year) return x.born.year < y.born.year;
	else if (x.born.month != y.born.month) return x.born.month < y.born.month;
	return x.born.day < y.born.day;
}
bool sosanhdeath(General x, General y) {
	if (x.death.era == "BC" && y.death.era == "AD") return true;
	else if (x.death.era == "AD" && y.death.era == "BC") return false;
	else if (x.death.year != y.death.year) return x.death.year < y.death.year;
	else if (x.death.month != y.death.month) return x.death.month < y.death.month;
	return x.death.day < y.death.day;
}
void insert(Node*& root, General x) {
	if (root == NULL) {
		root = makeNode(x);
		return;
	}
	if (sosanhborn(x, root->general)) {
		insert(root->left, x);
	}
	else if (!sosanhborn(x, root->general))
		insert(root->right, x);
	else if (sosanhdeath(x , root->general)) {
		insert(root->left, x);
	}
	else insert(root->right, x);
}
Node* prob2(vector<General> generals) {
	Node* root = NULL;
	for (int i = 0; i < generals.size(); i++) {
		insert(root, generals[i]);
	}
	return root;
}
//prob3----------------------------
string laybornyear(General x) {
	string temp = "";
	temp += to_string(x.born.year) + " " + x.born.era;
	return temp;
}
int prob3(Node* root, string born_year) {
	if (root == NULL) return 0;
	int cnt = 0;
	string temp = laybornyear(root->general);
	if (temp == born_year) ++cnt;
	cnt += prob3(root->left, born_year);
	cnt += prob3(root->right, born_year);
	return cnt;
}

//prob4----------------------------
Node* findnodenobattle(Node* root, string battle) {
	if (root == NULL) return NULL;
	findnodenobattle(root->left, battle);
	int cnt = 0;
	int j = 0;
	for (int i = 0; i < root->general.known_battles.size(); i++) {
		if (root->general.known_battles[i] != battle){
			++cnt;
		}
		++j;
	}
	if (cnt == j) findnodenobattle(root->right, battle);
	return root;
}
int demtrencaycobaonhieunodekhongthoaman(Node* root, string battle) {
	if (root == NULL) return 0;
	int cnt = 0;
	int j = 0;
	int tong = 0;
	for (int i = 0; i < root->general.known_battles.size(); i++) {
		if (root->general.known_battles[i] != battle) {
			++cnt;
		}
		++j;
	}
	if (cnt != j) ++tong;
	tong += demtrencaycobaonhieunodekhongthoaman(root->left, battle);
	tong += demtrencaycobaonhieunodekhongthoaman(root->right, battle);
	return tong;

}
void prob4(Node*& root, string battle) {
	if (root == NULL) return;
	for (int i = 0; i < demtrencaycobaonhieunodekhongthoaman(root, battle); i++) {
		Node* temp = findnodenobattle(root, battle);
		if (temp->left == NULL) {
			Node* temp2 = temp->right;
			delete temp;
			temp = temp2;
		}
		else if (temp->right == NULL) {
			Node* temp2 = temp->left;
			delete temp;
			temp = temp2;
		}
		else {
			Node* thaythe = findnodenobattle(root->right, battle);
			temp = thaythe;
			delete temp;
			prob4(root->right, battle);
		}
	}
}
int main()
{
}