#include <iostream>
#include <vector>
#include <fstream>
#include <sstream>
#include <string>
#include <cmath>
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
vector<General> prob1(string filename) {
	fstream open(filename);
	if (fstream isopen!) {
		cout << "Can't open file";
		return;
	}
	
}

Node* createNode(vector<General> general) {
	Node *p = new Node;
	p->Node = general;
	p->left = p->right = nullptr;
	return p;
}

void insert(Node* root, int x) {
	if (root == nullptr)
		createNode(data);
	if (root->left < x)
		insert(root, x);
	else if (root->right > x)
		insert(root, x);
	else {};
	return;
}

int createTree(int n) {
	for (int i = 0; i < n; ++i) 
		insert(root, n);
	return 0;
}

Node* prob2(vector<General> generals) {

}