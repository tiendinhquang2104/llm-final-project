#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
using namespace std;

struct Battle {
    string name, location;
    string from_date, to_date;
    int total_famous_generals;
    string* list_famous_generals;
};

int countLine(string filename){
    int n = 0;
    string line;
    ifstream fin(filename);
    while (getline(fin, line)){
        if (line.find_first_not_of(" \t\r\n") == string::npos) continue;
        n++;
    }
    return n-1;
}

string* countGeneral(string line, int &totalGeneral){
    int n = 0;
    string tmp;
    stringstream ss(line);
    while (getline(ss, tmp, ';')){
        n++;
    }
    ss.clear();
    ss.seekg(0, ios::beg);
    string* s = new string[n];
    totalGeneral = n;
    for (int i=0; i<n; i++){
        getline(ss, s[i], ';');
    }  
    return s;
}

Battle* prob1(string filename, int& n){
    n = countLine(filename);
    ifstream fin(filename);
    Battle* b = new Battle[n];
    string line;
    int i=0;
    getline(fin, line);
    while (getline(fin, line)){
        if (line.find_first_not_of(" \t\r\n") == string::npos) continue;
        stringstream ss(line);
        string tmp;
        getline(ss, tmp, ',');
        b[i].name = tmp;
        getline(ss, tmp, ',');
        b[i].location = tmp;
        getline(ss, tmp, ',');
        b[i].from_date = tmp;
        getline(ss, tmp, ',');
        b[i].to_date = tmp;
        getline(ss, tmp, ',');
        getline(ss, tmp, ',');
        getline(ss, tmp, ',');
        b[i].list_famous_generals = countGeneral(tmp, b[i].total_famous_generals);
        i++;
    }
    fin.close();
    return b;
}

struct Node {
    Battle battle;
    Node* next;
};

Node* createNode(Battle b){
    Node* p = new Node;
    p->battle = b;
    p->next = nullptr;
    return p;
}

void addtail(Node* &head, Battle b){
    if (head==nullptr){
        Node* p = createNode(b);
        head = p;
        return;
    }
    Node* cur = head;
    while (cur->next != head){
        cur = cur->next;
    }
    Node* p = createNode(b);
    cur->next = p;
}

Node* prob2(Battle* battles, int n){
    Node* head = nullptr;
    for (int i=0; i,n; i++){
        addtail(head, battles[i]);
    }
    return head;
}

int prob3(Node* head, string start_year, string end_year){

}

void prob4(Node*& head, string general){
    Node* cur = head;
    while (cur != nullptr){
        for (int i=0; i<cur->battle.total_famous_generals; i++){
            if (cur->battle.list_famous_generals[i] == general) break;
        }
        if (head == cur){
            Node* 
        }

        cur = cur->next;
    }
}
