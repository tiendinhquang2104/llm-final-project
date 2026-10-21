#include <iostream>
#include <fstream>
#include <string>
#include <sstream>
#include <istream>
#include <cstring>
#include <cmath>

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

//Problem 1
General* prob1(string filename, int& n);
General* prob1(string filename, int& n){
	General g[n];
	Date d_born[n];
	Date d_death[n];
	string total[n];
	string temp;
	char abc[1000];
	int i = 0;
	int count = 0;
	string header;
	fstream file(filename);
	getline(file, header); //To remove header
	while(!file.eof()){
		getline(file, g[i].name, ',');
		getline(file, g[i].nationality, ',');
		getline(file, temp, '-');
		d_born[i].month = stoi(temp);
		getline(file, temp, '-');
		d_born[i].day = stoi(temp);
		getline(file, temp, ' ');
		d_born[i].year = stoi(temp);
		getline(file, d_born[i].era, ',');
		d_death[i].month = stoi(temp);
		getline(file, temp, '-');
		d_death[i].day = stoi(temp);
		getline(file, temp, ' ');
		d_death[i].year = stoi(temp);
		getline(file, d_death[i].era, ',');
		getline(file, total[i], ',');
		getline(file, *g[i].known_battles, ',');
		getline(file,temp, ',');
		getline(file,temp, ',');
		getline(file,temp, ',');
		getline(file,temp, '\n');
		i++;
	}
	for (int m = 0; m < n; m++){
			for (int p = 0; p < n; p++){
//				abc[p] = stoc(total[m]);
				if (abc[p] == '|') count++;
			}
	count = g[i].total_known_battles;	
	}
	General* tempp = &g[0];
	return tempp;
}


//Problem 2
Node* CreateNode(General* generals){
	Node* NewNode;
//	NewNode->general = generals;
	NewNode->next = nullptr;
	return NewNode;
}

Node* prob2(General* generals, int n){
	Node* head = nullptr;
	Node* tail = nullptr;
	Node* temp = nullptr;
	for(int i = 0; i < n; i++){
		Node* NewNode = CreateNode(generals);
		if (i == 0){
			head = NewNode;
			head->next = nullptr;
		}else if(i == 1){
			temp = NewNode;
			head->next = temp;
			continue;
		}
			temp->next = NewNode;
			temp = NewNode;
			temp->next = nullptr;
	}
	return head;
}
//Problem 3
General prob3(Node* head);

//Problem 4
void prob4(Node*& head, string nationality);
