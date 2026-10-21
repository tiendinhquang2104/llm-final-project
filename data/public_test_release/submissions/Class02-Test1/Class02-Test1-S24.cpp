#include<iostream>
#include<fstream>
#include<sstream>
#include<string>
using namespace std;
int countline(string filename){
	ifstream fin(filename);
	int count = 0;
	string line;
	getline(fin,line);
	while(getline(fin,line,'\n')){
		count++;
	}
	fin.close();
	return count;
}
struct Battle{
	string name, location;
	string from_date, to_date;
	int total_famous_generals;
	string* list_famous_generals;
};

struct Node{
	Battle  battle;
	Node* next;
};

void addHead(Node*& head, Battle ans){
	Node*p = new Node;
	p->battle = ans;
	p->next = nullptr;
	p->next = head;
	head = p;
}


void printlist(Node* head){
	Node* cur = head;
	while(cur != nullptr){
		cout << cur->battle.name << endl;
		cur =cur->next;
	}
}
void split(string data, string*& list, int& count){
	count = 1;
	for(char c : data) if(c == ';') count++;
	int i = 0;
	list = new string[count];
	stringstream ss(data);
	string tmp;
	while(getline(ss,tmp,';')){
		list[i] = tmp;
		i++;
	}
}
Battle* prob1(string filename, int& n){
	n = countline(filename);
	ifstream fin(filename);
	string line;
	Battle* ans = new Battle[n];
	getline(fin,line);
	int i = 0;
	while(getline(fin,line) && i < n){
		stringstream ss(line);
		string tmp;
	    getline(ss,ans[i].name,',');
	    getline(ss,ans[i].location,',');
	    getline(ss,ans[i].from_date,',');
	    getline(ss,ans[i].to_date,',');
	    getline(ss,tmp,',');
	    getline(ss,tmp,',');
	    getline(ss,tmp);
	    split(tmp,ans[i].list_famous_generals,ans[i].total_famous_generals);
	    i++;
	}
	return ans;
	
}
Node* prob2(Battle* ans, int n){
	Node* head = nullptr;
	for(int i = 0; i < n; i++){
		addHead(head,ans[i]);
	}
	return head;
}
int main(){
	int n = countline("50-european-battles-first-20.csv");
	Battle* result = prob1("50-european-battles-first-20.csv",n);
	Node* head = prob2(result,n);
	printlist(head);
	
	return 0;
}
