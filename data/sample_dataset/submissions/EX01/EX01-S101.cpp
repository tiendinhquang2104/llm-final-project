#include <iostream>
#include <string>
#include <fstream>
#include <sstream>
#include <cstring>
#include <cmath>

using namespace std;

struct Date{
	int day, month, year;
	string era;
};

Date parseDate(string date){
	Date result;
	stringstream ss(date);
	string temp;
	getline(ss, temp, '-');
	result.month = stoi(temp);
	getline(ss, temp, '-');
	result.day = stoi(temp);
	getline(ss, temp, ' ');
	result.year = stoi(temp);
	getline(ss, temp);
	result.era = temp;
	return result;
}

struct General{
	string name, nationality;
	Date born, death;
	int total_known_battles;
	string* known_battles;
};

struct Node{
	General general;
	Node* next;
};

Node* createNode(General x){
	Node* newNode = new Node();
	newNode->general = x;
	newNode->next = nullptr;
	return newNode;
}

string* split(string s, char delimiter, int& n){
	n = 1;
	for (char& c : s){
		if (c == delimiter){
			n++;
		}
	}
	
	string* temp = new string[n];
	stringstream ss(s);
	string word;
	int i = 0;
	while(getline(ss, word, delimiter)){
		temp[i++] = word;
	}
	return temp;
}

void addTail(Node*& head, General x){
	Node* newNode = createNode(x);
	if (head == nullptr){
		head = newNode;
		return;
	}
	Node* temp = head;
	while(temp->next != nullptr){
		temp = temp->next;
	}
	temp->next = newNode;
}

General* prob1(string filename, int& n){
	string header;
	fstream inFile(filename);
	getline(inFile, header);
	General* x = new General[n];
	string line;
	int i = 0;
	while(getline(inFile, line)){
		stringstream ss(line);
		getline(ss, x[i].name, ',');
		getline(ss, x[i].nationality, ',');
		string dateStr;
		getline(ss, dateStr, ',');
		x[i].born = parseDate(dateStr);
		getline(ss, dateStr, ',');
		x[i].death = parseDate(dateStr);
		string knownB;
		getline(ss, knownB, ',');
		x[i].known_battles = split(knownB, '|', x[i].total_known_battles);
		
		i++;
	}
	
	inFile.close();
	return x;
}

Node* prob2(General* generals, int n){
	Node* head = nullptr;
	for(int i = 0; i < n; i++){
		addTail(head, generals[i]);
	}

	return head;
}

void prob4(Node*& head, string nationality){
	if (head == nullptr) return;
	Node* temp = head;
	while(temp != nullptr){
		if (temp->general.nationality == nationality){
			Node* deleted = temp;
			temp = deleted->next;
			delete deleted;
		}
		else {
			temp = temp->next;
		}
	}
}

int main(){
	string filename = "50-best-european-generals-cleaned-first-20.csv";
	int n = 21;
	General* x = new General[n];
	x = prob1(filename, n);
	prob2(x, n);
	return 0;
}
