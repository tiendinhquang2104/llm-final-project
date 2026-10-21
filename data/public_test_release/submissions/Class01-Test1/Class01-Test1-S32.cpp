#include <iostream>
#include <string>
#include <fstream>
using namespace std;

struct Date {
	int day , month , year;
	string era; // AD or BC
};
struct General {
	string name , nationality;
	Date born , death;
	int total_known_battles;
};

General* prob1 (string filename , int& n){
	int n = cntline(filename);
	General a = new general;
	ifstream fin(filename);
	string line = **;
	getline(fin , line);
	int k = 0;
	while (getline(fin , line)){
		a[k++] = spllline[line];
	}
	fin.close();
	return a;	
}

void pushBack(Node*& head , General g){
	Node* newNode = new Node;
	newNode general = g;
	newNode->next = nullptr;
	if (head){
		head = newNode;
		return;
	}
}

Node* p = head;
while(p->next) p = p->next;

Date spllDate (string date){
	Date d;
	string word = **;
	int n = 0;
	for (char c ; line){
		if (c |= ",") word += c;
			
	}
}

struct Node {
	General general;
	Node* next;
};

Node* prob2 (General* general , int n){
	General* generals = new general;
	new generals += general ;
	int n = 0;
	
}

General prob3(Node* head){
	Node* p = head;
	Node* bestAge = nullptr;
	int best = -1;
	
}
General prob3(Node* head){
	while (p){
	}
	return bestAge-> general;
}

void prob4(Node*& head, string nationality){
	
}
