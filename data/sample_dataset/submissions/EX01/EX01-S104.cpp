#include<iostream>
#include<fstream>
#include<string>
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
int countline(string filename) {
	ifstream filein(filename); 
	string line; 
	int cnt = 0; 
	getline(filein, line); 
	while (getline(filein, line))
		cnt++; 
	filein.close(); 
	return cnt; 
}
struct Node {
	General general;
	Node* next;
};
General* prob1(string filename, int& n) {
	ifstream filein(filename);
	n = countline(filename); 
	string line; 
	getline(filein, line); 
	General* a = new General[n]; 
	for (int i = 0; i < n; i++) {
		getline(filein, a[i].name,',');
		getline(filein, a[i].nationality, ','); 
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
		a[i].known_battles = new string; 
		getline(filein,a[i].known_battles[0], ',');
		getline(filein, line, ','); 
		getline(filein, line, ',');
		getline(filein, line, ','); 
		getline(filein, line);
		a[i].total_known_battles = stoi(line); 
	}
	filein.close(); 
	return a; 
}
Node* createnode(General gr) {
	Node* p = new Node; 
	p->general = gr; 
	p->next = NULL; 
	return p; 
}
Node* prob2(General* generals, int n) {
	Node* Head = createnode(generals[0]); 
	Node* tail = Head; 
	for (int i = 1; i < n; i++) {
		Node* p = createnode(generals[i]); 
		tail->next = p; 
		tail = p; 
	}
	delete[] generals; 
	return Head; 
}
int countage(Node* p) {
	int age; 
	if (p->general.born.era == "AD") {
		age = p->general.death.year - p->general.born.year; 
	}
	else if (p->general.born.era == "BC") {
		age = 100-(p->general.born.year) + p->general.death.year;
	}
	return age; 
}
General prob3(Node* head) {
	int max = 0; 
	for (Node* k = head; k != NULL; k = k->next) {
		if (countage(k) > max)
			max = countage(k); 
	}
	for (Node* k = head; k != NULL; k = k->next) {
		if (countage(k) == max) {
			return k->general; 
		}
	}
}
void prob4(Node*& head, string nationality) {
	while (head != NULL && head->general.nationality == nationality) {
		Node* tam = head; 
		head = head->next; 
		delete tam; 
	}
	if (head == NULL)
		return;
	Node* pre = head; 
	for (Node* cur = head->next; cur != NULL; ) {
		if (cur->general.nationality == nationality) {
			pre->next = cur->next; 
			delete cur; 
			cur = pre->next; 
		}
		else {
			pre = cur; 
			cur = cur->next; 
		}
	}
}
int main() {
	string filename = "50-best-european-generals-cleaned-first-20.txt"; 
	ifstream filein(filename); 
	int n = countline(filename); 
	General* a = prob1(filename, n); 
	Node* Head = prob2(a, n); 
	prob4(Head, "England"); 
	cout << prob3(Head).name; 
}