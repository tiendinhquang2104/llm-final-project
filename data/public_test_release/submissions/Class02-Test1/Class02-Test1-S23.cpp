#include<iostream>
#include<sstream>
#include<fstream>
#include<string>
using namespace std;


struct Battle {
	string name, location;
	string from_date, to_date;
	int total_famous_generals;
	string* list_famous_generals;
};

struct Node {
	Battle battle;
	Node* next;
};

struct Date{
	int d,m,y;
};

Node* create (Battle x){
	Node *p = new Node;
	p->battle = x;
	p->next=NULL;
	return p;
}


void addlast (Node*&head,Battle x){
	Node *p=create(x);
	if (head==NULL){
		head=p;
		return;
	}
	
	Node *q=head;
	while (q->next !=0){
		q=q->next;
	}
	q->next = p;
}

int countfile(string filename){
	int count=0;
	ifstream fin (filename);
	string line;
	getline(fin,line);
	
	while(getline(fin,line)){
		count++;
	} 
	fin.close();
	return count;
}

Battle readData(string line){
	Battle x;
	string tmp;
	string temp;
	string t;
	stringstream ss(line);
	
	getline(ss,x.name,',');
	getline(ss,x.location,',');
	getline(ss,x.from_date,',');
	getline(ss,x.to_date,',');
	getline(ss,tmp,',');
	getline(ss,tmp,',');
	getline(ss,tmp,'\n');
	
	*x.list_famous_generals =tmp;
	
	int count=0;
	int n=0;
	while  (getline(ss,temp,',')){
		n++;
		if (n==6){
			while(getline(ss,t,';')){
				count++;
			}
		}
	}

	x.total_famous_generals=count;
	
	return x;
}

Date split(string line){
	Date t;
	char dash;
	stringstream ss(line);
	
	ss>>t.d>>dash>>t.m>>dash>>t.y;
	return t;
}

Battle* prob1(string filename, int& n){
	ifstream fin(filename);
	string line;
	n=countfile(filename);
	getline(fin,line);
	Battle*head=NULL;
	
	while(getline(fin,line)){
		*head= readData(line);
		
	}
	
	fin.close();
	return head;
}

Node* prob2(Battle* battles,int n){
	Node* head=NULL;
	for (int i=0;i<n;i++){
		addlast(head,battles[i]);
	}
	
	return head;
}

int prob3(Node* head, string start_year, string end_year){
	int count=0;
	Date t1 = split(start_year);
	Date t2 = split(end_year);
	while (head!=NULL){
		if (head->battle.from_date >=start_year && head->battle.to_date<=end_year){
			count++;
		}
		
		head=head->next;
	}
	
	return count;

}
