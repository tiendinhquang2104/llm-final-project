#include <iostream>
#include <fstream>
#include <cstring>
#include <sstream>
#include <string>
using namespace std;
struct Date{
	int day, month, year;
	string era;
	
};
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
General* prob1(string filename, int &n){
	ifstream fin(filename);
	if(!fin.is_open()){
	n = 0;
	return NULL;
}	
	string line;
	getline(fin, line);
	
	while(getline(fin, line)) n++;
	
	fin.clear();
	fin.seekg(0);
	
	getline(fin, line);
	General* arr = new General[n];
	int i = 0;
	while(getline(fin, line)){
		stringstream ss(line);
		
		getline(ss, arr[i].name, ',');
		getline(ss, arr[i].nationality, ',');
		
		string temp0;
		getline(ss, temp0, ',');
		stringstream ss1(temp0);
		string temp;
		getline(ss1, temp, '-');
		arr[i].born.day = stoi(temp);
		getline(ss1, temp, '-');
		arr[i].born.month = stoi(temp);
		getline(ss1, temp, '-');
		arr[i].born.year = stoi(temp);
		getline(ss1, arr[i].born.era);
		
		string temp00;
		getline(ss, temp00, ',');
		stringstream ss2(temp00);
		string temp1;
		getline(ss2, temp1, '-');
		arr[i].death.day = stoi(temp1);
		getline(ss2, temp1, '-');
		arr[i].death.month = stoi(temp1);
		getline(ss2, temp1, '-');
		arr[i].death.year = stoi(temp1);
		getline(ss2, arr[i].death.era);
		
		getline(ss, *arr[i].known_battles, ',');
		string temp3;
		string temp4;
		getline(ss, temp3, ',');
		getline(ss, temp4, ',');
		string temp5;
		getline(ss, temp5);
		arr[i].total_known_battles = stoi(temp5);
		i++;
	}
	fin.close();
	return arr;
}
Node* prob2(General* generals, int n){
	Node* head =  new General{generals[0], NULL};
	Node* tail = head;
	if (n == 0) return NULL;
	for(int i = 1 ; i < n; i++){
		Node* p = new General{generals[i], NULL};
		tail->next = p;
		tail = p;
	}
	return head;
}
void prob4(Node*& head, string nationality){
	if( head != NULL && head->general.nationality == nationality){
		Node* temp = head;
		head = head->next;
		delete temp;
	}
	Node* prev = head;
	while( curr != NULL){
		Node* curr = head->next;
		if (curr->general.nationality == nationality){
			prev->next = curr->next;
			delete curr;
		}
		else{
			prev = curr;
			curr = curr->next;
		}
	}
}


