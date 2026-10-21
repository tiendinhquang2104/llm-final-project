#include <iostream>
#include <fstream>
#include <string>
using namespace std;
struct Battle {
	string name;
	string year;
	string general;
};
struct Node{
	Battle batlle;
	Node* next;
};
Battle* prob1(string filename, int n){
	ifstream file("50-european-battles-first-20.csv");
	if (!file.is_open()){
		n=0;
		return nullptr;
	}
	if (!file >>n) return nullptr;
	file.ignore();
	Battle*battles = new Battle[n];
	for (int i=0; i<n; i++){
		getline (file, battles[i].name);
		getline (file, battles[i].year);
		getline (file, battles[i].general);
	}
	file.close();
	return battles;
}


Node* prob2(Battle*battles, int n){
	if (n<=0 || battles == nullptr){
	Node* head = new Node{battles[0], nullptr};
	Node* current = head;
	for (int i =1; i<n; i++){
	current->next = new Node(battles[i], nullptr);
	current = current->next;
	}
	return head;
}


int prob3(Node*head, string start_year, string end_year){
	int count =0;
	Node* current = head;
	while (current != nullptr){
		if (current->Battle.year >= start_year&& current->Battle.year <= end_year){
			count++;
		}
		return count;
	}
}


void prob4(Node*& head, string general)
