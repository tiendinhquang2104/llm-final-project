
#include <iostream>
#include <string>
#include <fstream>
#include <cmath>
#include <sstream>
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

// prob1-----------------------------------------
struct Node {
	General general;
	Node* next;
};
Node* makeNode(General x) {
	Node* newNode = new Node;
	newNode->general = x;
	newNode->next = NULL;
	return newNode;
}
Date tachngaythangnam(string s) {
	Date res;
	if (s[0] == '0') {
		res.day = s[1];
	}
	else {
		string tmp;
		for (int i = 0; i <= 1; i++) {
			tmp += s[i];
		}
		res.day = stoi(tmp);
	}
	if (s[3] == '0') {
		res.month = s[4];
	}
	else {
		string tmp;
		for (int i = 3; i <= 4; i++) {
			tmp += s[i];
		}
		res.day = stoi(tmp);
	}
	string temp3;
	for (int i = 6; i <= 9; i++) {
		temp3 += s[i];
	}
	res.year = stoi(temp3);
	for (int i = 11; i <= 12; i++){
		res.era += s[i];
	}
	return res;
}
General* prob1(string filename, int& n) {
	fstream f;
	f.open(filename);
	if (!f.is_open()) {
		n = 0;
		return NULL;
	}
	int temp = 0;
	string line;
	getline(f, line); // header;
	while (getline(f, line)) ++temp;
	f.clear();
	f.seekg(0, ios::beg);
	General* a = new General[temp];
	int idx = 0;
	getline(f, line); // header
	while (idx < temp) {
		General g;
		string tmp1, tmp2;
		getline(f, g.name, ',');
		getline(f, g.nationality, ',');
		getline(f, tmp1, ',');
		g.born = tachngaythangnam(tmp1);
		getline(f, tmp2, ',');
		g.death = tachngaythangnam(tmp2);
		string trashlistofmedal, trashknownposition, trashlastposition;
		getline(f, trashlistofmedal, ',');
		getline(f, trashknownposition, ',');
		getline(f, trashlastposition, ',');
		string tmp3;
		getline(f, tmp3);
		g.total_known_battles = stoi(tmp3);
		a[idx++] = g;
	}
	n = temp;
	f.close();
	return a;
}
// problem2-------------
void pushback(Node*& head, General x) {
	Node* newNode = makeNode(x);
	if (head == NULL) {
		head = newNode;
		return;
	}
	Node* current = head;
	while (current->next) {
		current = current->next;
	}
	current->next = newNode;
}

Node* prob2(General* generals, int n) {
	Node* head = NULL; // init
	for (int i = 0; i < n; i++) {
		pushback(head, generals[i]);
	}
	return head;
}
// prob3-----------------------------
General prob3(Node* head) {
	General res;
	int ans = -100000000;
	while (head) {
		int d = head->general.death.year;
		int b = head->general.born.year;
		int kq = abs(d - b);
		if (kq > ans) {
			ans = kq;
			res = head->general;
		}
	}
	return res;
}

//prob4-------------------------
void prob4(Node*& head, string nationality) {
	if (head != NULL && head->general.nationality == nationality) {
		Node* temp = head;
		head = head->next;
		delete temp;
	}
	if (head == NULL) {
		return;
	}
	Node* prev = head;
	Node* current = head->next;
	while (current->next) {
		if (current->general.nationality == nationality) {
			Node* temp = current;
			prev->next = current->next;
			current = current->next;
			delete temp;
		}
		else {
			prev = current;
			current = current->next;
		}
	}
}
int main()
{
}
