#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
#include <cstring>
#include <cmath>
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

/*Node* createNode(Node*, int data) {
	Node* p = new Node;
	p->general.total_known_battles == data;
	p->next = nullptr;
	return p;
}*/

General* prob1(string filename, int& n) {
	ifstream fin(filename);
	fin.open(filename);
	int General[]{n};
	if (!fin.is_open()) {
		cout << "cannot open file" << endl;
		return nullptr;
	};
	if (fin.is_open())	{
		for (int i = 0; i < n; ++i) {
			fin >> General[i];
		};
		cout << "file is open" << endl;
	};
	fin.close();
	return nullptr;
}




