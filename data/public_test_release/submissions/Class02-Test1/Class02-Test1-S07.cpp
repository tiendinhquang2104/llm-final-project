#include<iostream>
#include<fstream>
#include<string>
#include<sstream>
using namespace std;

struct Date { int day, month, year; };

struct Node {
	Battle battle;
	Node* next;
};
struct Battle {
	string name, location;
	string from_date, to_date;
	int total_famous_generals;
	string* list_famous_generals;
};
Date* splitData(string line) {
	t.day = stoi(line, substr(0, 2));
	t.month = stoi(line, substr (3, 2));
	t.year = stoi(line, substr (6, 4));
	return t;
}
int countLine(string filename) {
	int count=0;
	string line;
	fstream fin(filename);
	getline(fin, line);
	while (getline(fin, line)) {
		count++;
	}
	return count;
}
Battle* prob1(string filename, int& n) {
	//n = countLine(filename);
	//fstream fin(filename);
	//for (int i = 0, i < n, i++) {
		//getline(fin, Battle.name, ',');
	}
Node* prob2(Battle* battles, int n) {

}
void addTail() {

}

Node* createList() {

}
Node* printList() {

}
