#include<iostream>
#include<fstream>
#include<string>
#include<cmath>

using namespace std;

struct Date {
	int day, month, year;
	string era; // AD or BC
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


//Prob1: 
string getfield(string& line) {
	size_t pos = line.find(',');
	string field;

	if (pos == string::npos) {
		field = line;
		line = "";
	}
	else {
		field = line.substr(0, pos);
		line.erase(0, pos + 1);
	}

	return field;
}
General* prob1(string filename, int& n) {
	fstream fin(filename);
	if (!fin) {
		n = 0;
		return nullptr;
	}

	string line;
	n = 0;

	getline(fin, line);
	while (getline(fin, line)) {
		if (!line.empty()) n++;
	}
	fin.close();

	fin.open(filename);
	getline(fin, line);

	General* arr = new General[n];
	int i = 0;

	while (getline(fin, line)) {
		arr[i].name = getfield(line);
		arr[i].nationality = getfield(line);
		arr[i].born.era = getfield(line);
		arr[i].death.era = getfield(line);
		if (line == "") {
			arr[i].total_known_battles = 0;
		}
		else {
			arr[i].total_known_battles = stoi(line);
		}

		i++;
	}

	fin.close();
	return arr;
}

//Prob2: 
Node* prob2(General* generals, int n) {
	if (generals == nullptr || n == 0) return nullptr;

	Node* head = new Node{ generals[0], nullptr };
	Node* tail = head;

	for (int i = 1; i < n; i++) {
		Node* p = new Node{ generals[i], nullptr };
		tail->next = p;
		tail = p;
	}

	return head;
}

//Prob3:
int getyear(string born) {
	string year = "";

	for (int i = born.length() - 1; i >= 0; i--) {
		if (isdigit(born[i])) year = born[i] + year;
		else if (!year.empty()) break;
	}

	if (year == "") return -1;
	return stoi(year);
}
General prob3(Node* head);

//Prob4:
void prob4(Node*& head, string nationality) {
	if (head == nullptr) return;

	while (head != nullptr && head->general.nationality == nationality) {
		Node* tmp = head;
		head = head->next;
		delete tmp;
	}

	Node* prev = head;
	Node* cur = (head ? head->next : nullptr);

	while (cur != nullptr) {
		if (cur->general.nationality == nationality) {
			prev->next = cur->next;
			delete cur;
			cur = prev->next;
		}
		else {
			prev = cur;
			cur = cur->next;
		}
	}
}
