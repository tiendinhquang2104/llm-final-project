#include <fstream>
#include <sstream>
#include <string>
using namespace std;
struct Battle {
string name, location;
string from_date, to_date;
int total_famous_generals;
string* list_famous_generals;
}
struct Node {
Battle battle;
Node* next;
};
Battle* prob1(string filename, int& n){
	cin>>n;
	Battle*tmp = new Battle[n];
	ifstream fin(filename);
	count = 0;
	string line;
	while(getline(fin,line)){
		stringstream ss;
		string temp;
		getline(ss,temp,",")
		tmp[count].name=stof(temp);
		getline(ss,temp,",")
		tmp[count].location=stof(temp);
		getline(ss,temp,",")
		tmp[count].from_date=stof(temp);
		getline(ss,temp,",")
		tmp[count].to_date=stof(temp);
		getline(ss,temp,",")
		tmp[count].total_famous_generals=int(atof(temp));
		getline(ss,temp,",")
		tmp[count].list_famous_generals=temp;
		count++;
	}
	fin.close;
	return tmp;
}
Node* createnode(Battle x){
	Node*p= new Node;
	p->battle= x;
	p->next= nullptr;
	return p;
}
Node* prob2(Battle* , int n){
	Node*head;
	head->battle = battles[0];
	head->next = nullptr;
	
	for(int i =1;i<n;i++){
		Node*p = createnode(battles[i]);
		Node*cur=head;
		
		while(cur->next!=nullptr){
			cur= cur->next;
		}
		cur->next = p;
	}	
}

