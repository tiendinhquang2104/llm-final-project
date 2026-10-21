#include <iostream>
#include <cstring>
#include <fstream>
using namespace std;
struct Battle{
	string name,location;
	string from_date,to_date;
	int total_famous_generals;
	string* list_famous_generals;
};
struct Node{
	Battle battle;
	Node*next;
};
void addTail(Node* &head, Read val) {
	Node* temp = new Node;

    temp->read = val;
    temp->next = nullptr;

    Node* curr = head;
    if (head == nullptr) {
        head = temp;
        return;
    }

    while (curr->next != nullptr) {
        curr = curr->next;
    }
    curr->next = temp;
}
Battle* probl(string filename,int& n);
Node* head=new Node();
head = nullptr;
    fstream fin;
    fin.open(fileName, ios::in);
    string s;
    getline(fin,s);
  while (getline(fin, s, ',')) {

        Transaction p;
        p.from_date = s;
        getline(fin, s, ',');
        p.to_date = s;
        getline(fin, s, ',');
        p.battlename = s;
        getline(fin, s, ',');
        p.location = s;
        getline(fin, s, ',');
        p.Countries = s;
        getline(fin, s, ',');
        p.Involved = s;
        getline(fin, s, ',');
        p.amount = atof(s.c_str());
        getline(fin, s);
        p.ListFamousGenerals = s;
        addTail(head, p);
    }
    fin.close();
    return head;
	

bool Node* probl2(Battle* battles,int n);
Node* temp = new Node;

    temp->read = val;
    temp->next = nullptr;

    Node* curr = head;
    if (head == nullptr) {
        head = temp;
        return;
    }

    while (curr->next != nullptr) {
        curr = curr->next;
    }
    curr->next = temp;
}
Battle* probl(string filename,int& n);
Node* head=new Node();
head = nullptr;
    fstream fin;
    fin.open(fileName, ios::in);
    string s;
    getline(fin,s);
  while (getline(fin, s, ',')) {

        Transaction p;
        p.from_date = s;
        getline(fin, s, ',');
        p.to_date = s;
        getline(fin, s, ',');
        p.battlename = s;
        getline(fin, s, ',');
        p.location = s;
        getline(fin, s, ',');
        p.Countries = s;
        getline(fin, s, ',');
        p.Involved = s;
        getline(fin, s, ',');
        p.amount = atof(s.c_str());
        getline(fin, s);
        p.ListFamousGenerals = s;
        addTail(head, p);
    }
    fin.close();
    return head;


int probl3(Node* head, string start_year, string end_year);
Node* totalnumber = head;
for(int i=0,i <= n, i++){
	totalnumber += i;
	Node* totalnumber =[i];
}
int in_place = totalnumber;
cout<<in_place<<endl;



void probl4(Node*& head, string general);
Node* general = head;

    while (general->next != nullptr) {
        if (!checkTime(general->transaction, general->next->transaction) || !(general->transaction.hash == general->next->transaction.prev_hash)) {
            Node* temp = general->next;
            general->next = temp->next;
            delete temp;
        }
        general = general->next;
    }

}

