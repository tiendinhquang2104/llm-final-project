#include <iostream>
#include<fstream>
#include<string>
#include<vector>
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
int countline(string filename) {
	ifstream filein(filename); 
	string line;
	getline(filein, line); 
	int cnt = 0; 
	while (getline(filein, line))
		cnt++; 
	return cnt; 
}
void split(string s, vector<string>& knowbattle) {
	vector<string> tam(s.size());
	string cur = "";
	int num = 0;
	for (int i = 0; i < s.size(); i++) {
		if (s[i] == '|') {
			tam[num++] = cur;
			cur = "";
		}
		else
			cur += s[i]; 
	}
	tam[num++] = cur; 
	for (int i = 0; i < num; i++) {
		knowbattle.push_back(tam[i]); 
	}
 }
vector<General> prob1(string filename) {
	ifstream filein(filename); 
	string line; 
	int n = countline(filename); 
	vector<General> a(n); 
	getline(filein, line); 
	for (int i = 0; i < n; i++) {
		getline(filein, a[i].name,',');
		getline(filein, a[i].nationality,',');
		getline(filein, line, '-'); 
		a[i].born.day = stoi(line); 
		getline(filein, line, '-'); 
		a[i].born.month = stoi(line); 
		getline(filein, line, ' '); 
		a[i].born.year = stoi(line); 
		getline(filein, a[i].born.era, ','); 

		getline(filein, line, '-');
		a[i].death.day = stoi(line);
		getline(filein, line, '-');
		a[i].death.month = stoi(line);
		getline(filein, line, ' ');
		a[i].death.year = stoi(line);
		getline(filein, a[i].death.era, ','); 
		getline(filein, line, ','); 
		split(line, a[i].known_battles); 
		getline(filein, line, ','); 
		getline(filein, line, ','); 
		getline(filein, line, ','); 
		getline(filein, line); 
	}
	return a; 
	 
}
Node* createnode(General x) {
	Node* p = new Node; 
	p->general = x; 
	p->left = NULL;
	p->right = NULL; 
	return p; 
}
General count_age(General x,General root) {
	if (x.born.era == "AD" && root.born.era == "BC")
		return root;
	if (x.born.era == "BC" && root.born.era == "AD")
		return x; 
	if (x.born.era == "BC") {
		if (x.born.year > root.born.year) 
			return x;
		else if (x.born.year < root.born.year)
			return root; 
		else {
			if (x.death.year > root.death.year)
				return x;
			else if (x.death.year < root.death.year)
				return root; 
		}
	}
	else {
		if (x.born.year > root.born.year)
			return root;
		else if (x.born.year < root.born.year)
			return x;
		else {
			if (x.death.year > root.death.year)
				return root;
			else if (x.death.year < root.death.year)
				return x;
		}
	}
}
void insert(Node*& root, General x) {
	if (root == NULL) {
		Node* p = createnode(x); 
		root = p; 
		return; 
	}
	if (x.born.era == "AD" && root->general.born.era == "BC")
		insert(root->left, x); 
	if (x.born.era == "BC" && root->general.born.era == "AD")
		insert(root->right,x);
	if (x.born.era == "BC") {
		if (x.born.year > root->general.born.year)
			insert(root->right, x);
		else if (x.born.year < root->general.born.year)
			insert(root->left, x);
		else {
			if (x.death.year > root->general.born.year)
				insert(root->right, x);
			else if (x.death.year < root->general.born.year)
				insert(root->left, x);
		}
	}
	else {
		if (x.born.year > root->general.born.year)
			insert(root->left,x);
		else if (x.born.year < root->general.born.year)
			insert(root->right,x);
		else {
			if (x.death.year > root->general.death.year)
				insert(root->left, x);
			else if (x.death.year < root->general.death.year); 
				insert(root->right, x);
		}
	}
}
Node* prob2(vector<General> generals) {
	Node* root = createnode(generals[0]); 
	string filename = "50-best-european-generals-cleaned-first-20.csv"
	int n = countline(filename); 
	for (int i = 0; i < n; i++) {
		insert(root, generals[i]); 
	}
	return root; 
}
int main() {
	string filename = "50-best-european-generals-cleaned-first-20.csv"; 
	cout << countline(filename) << endl; 
	vector<General> a = prob1(filename); 
	cout << a[19].known_battles[1]; 
	cout << a.size(); 
	
}


