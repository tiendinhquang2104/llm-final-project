#include <iostream>
#include <string>
#include <fstream>
#include <sstream>
#include <cstring>
using namespace std;

struct Battle{
	string name,location;
	string from_date,to_date;
	int total_famous_general;
	string *list_lamous_general;
};

struct Node{
	Battle battle;
	Node *next;
};

typedef struct Node* node;

node createnode(Battle name){
	node p=new Node;
	p->battle=name;
	p->next=NULL;
	return p;
}

void addtail(node a,Battle name){
	node p=createnode(name);
	if (a==NULL){a=p;}
	else {
		node i=a;
		while (i->next!=NULL){i=i->next;}
		i->next=p;
	}
}

void printlist(node a){
	node i=a;
	while (i->next!=NULL){
		cout << i->battle.name;
		i=i->next;
	}
}

Battle* prob1(string filename,int &n){
	node head=NULL;
	ifstream file;
	file.open("50-european-battles-first-20.csv");
	int a[100];
	int i=0;
	Battle s;
	while (getline(file,filename,'\n')){
		a[i]=s.name[i]; i++;
	}
	return s;
}

int sodong(string filename){
	ifstream file;
	file.open("50-european-battles-first-20.csv");
	int d=0;
	while (getline(file,filename,'\n')){
		d++;
	}
	return d;
}

Node* prob2(Battle *battles,int n){
	node a=NULL;
	ifstream file;
	file.open("50-european-battles-first-20.csv");
	string line;
	n=sodong(line);
	int i=0;
	while (getline(file,line,'\n')){
		
	}
}

int prob3(Node* head,string start_year,string end_year){
	node a=NULL;
	ifstream file;
	file.open("50-european-battles-first-20.csv");
	string line;
	int n=sodong(line);
	int i=0;
	while (getline(file,line,'\n')){
		
	}
}

void prob4(Node*& head,string general){
	node a=NULL;
	ifstream file;
	file.open("50-european-battles-first-20.csv");
	string line;
	int n=sodong(line);
	int i=0;
	while (getline(file,line,'\n')){
		
	}
}

int main(){
	node head=NULL;
	ifstream file;
	file.open("50-european-battles-first-20.csv");
	string line;
	int n=sodong(line);
	cout << prob1(line,n).name;
	printlist(head);
	file.close();
	return 0;
}
