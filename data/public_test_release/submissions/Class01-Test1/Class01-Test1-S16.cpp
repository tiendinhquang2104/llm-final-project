#include <iostream>
#include <sstream>
#include <string>
#include <fstream>
#include <cstring>
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

struct Node {
	General general;
	Node* next;
};

General* prob1(string filename, int& n){
	ifstream file(filename);
	if(!file.is_open()){
		n = 0;
		return nullptr;
	}
	string line;
	int cnt;
	getline(file, line);
	while(getline(file, line)){
		if(!line.empty()){
			cnt++;
		}
	}
	n = cnt;
	if(n == 0) return nullptr;
	file.clear();
	file.seekg(0);
	General* g = new General[n];
	int i = 0;
	getline(file, line);
	while(getline(file, line) && i < n){
		string segment, s;
		stringstream ss(line);
		getline(ss, g[i].name, ',');
		getline(ss, g[i].nationality, ',');
		getline(ss, segment, '-');
		g[i].born.day = stoi(segment);
		getline(ss, segment, '-');
		g[i].born.month = stoi(segment);
		getline(ss, segment, ' ');
		g[i].born.year = stoi(segment);
		getline(ss, g[i].born.era, ',');
		getline(ss, segment, '-');
		g[i].death.day = stoi(segment);
		getline(ss, segment, '-');
		g[i].death.month = stoi(segment);
		getline(ss, segment, ' ');
		g[i].death.year = stoi(segment);
		getline(ss, g[i].death.era, ',');
		getline(ss, s, ',');
		g[i].known_battles = &s;
		getline(ss, segment, ',');
		getline(ss, segment, ',');
		getline(ss, segment, ',');
		getline(ss, segment);
		g[i].total_known_battles = stoi(segment);
		i++;
	}
	file.close();
	return g;
}

Node* prob2(General* generals, int n){
	if(generals == nullptr || n <= 0) return nullptr;
	Node* head = new Node;
	head->general = generals[0];
	head->next = nullptr;
	Node* cur = head;
	for(int i = 1; i < n; i++){
		Node* newnode = new Node;
		newnode->general = generals[i];
		newnode->next = nullptr;
		cur->next = newnode;
		cur = cur->next;
	}
	return head;
}

General prob3(Node* head){
	Node* cur = head;
	int max = 0;
	int y;
	while(cur!= nullptr){
		if(cur->general.born.era == cur->general.death.era){
			if(cur->general.born.era == "AD"){
				y = cur->general.death.year - cur->general.born.year;
				if(y > max) max = y;}
			else{
				y = - cur->general.death.year + cur->general.born.year;
				if(y > max) max = y;
			}
		}
		else{
				y = cur->general.death.year + cur->general.born.year;
				if(y > max) max = y;
			}
		cur = cur->next;
	}
	cur = head;
	while(cur!= nullptr){
		if(cur->general.born.era == cur->general.death.era){
			if(cur->general.born.era == "AD"){
				y = cur->general.death.year - cur->general.born.year;
				if(y == max) return cur->general;}
			else{
				y = - cur->general.death.year + cur->general.born.year;
				if(y == max) return cur->general;
			}
		}else{
			y = cur->general.death.year + cur->general.born.year;
			if(y == max) return cur->general;
		}
		cur = cur->next;
}}

void prob4(Node*& head, string nationality){
	if(head == nullptr) return;
	while(head != nullptr || head->general.nationality == nationality){
		Node* tmp = head;
		head = head->next;
		delete tmp;
	}
	if(head == nullptr) return;
	Node* cur = head;
	while(cur!= nullptr){
		if(cur->next->general.nationality == nationality){
			Node* tmp = cur->next;
			cur->next = tmp->next;
			delete tmp;
		}else{
			cur = cur->next;
		}
	}
}

int main(){
	return 0;
}



