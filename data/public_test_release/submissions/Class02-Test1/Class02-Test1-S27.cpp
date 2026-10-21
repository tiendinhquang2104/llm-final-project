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
struct Node {
    Battle battle;
    Node* next;
};

int countline(string filename){
    int count = 0;
    ifstream fin;
    fin.open(filename);
    string line;
    getline(fin, line);
    while(getline(fin, line)){
        count++;
    }
    fin.close();
    return count;
}

string* readline(string filename, int n){
    string* ans = new string [n];
    ifstream fin;
    string line;
    fin.open(filename);
    getline(fin, line);
    int i = 0;
    while(getline(fin, line)){
        ans[i++] = line;
    }
    fin.close();
    return ans;
}

string* split_gen(string line, int &n){
    stringstream ssCount (line);
    string tmp;
    n = 0;
    while(getline(ssCount, tmp, ';')){
        n++;
    }
    string* a = new string [n];
    stringstream ssData(line);
    while(getline(ssData, tmp, ';')){
        a[n] = tmp;
        n++;
    }
    return a;
}

Battle* prob1(string filename, int& n){
    Battle* ba = new Battle [n];
    string* a = readline(filename, n);
    for(int i = 0; i < n; i++){
        stringstream ss (a[i]);
        string tmp;
        getline(ss, ba[i].name, ',');
        getline(ss, ba[i].location, ',');
        getline(ss, ba[i].from_date, ',');
        getline(ss, ba[i].to_date, ',');
        getline(ss, tmp, ',');
        getline(ss, tmp, ',');
        getline(ss, tmp, ','); ba[i].list_famous_generals = split_gen(tmp, ba[i].total_famous_generals);
        
    }
    return ba;

}

Node* createnode(Battle b){
    Node*p = new Node;
    p->battle = b;
    p->next = nullptr;
    return p;
}

void addTail(Node* head, Battle b){
    Node* p = createnode(b);
    if(head == nullptr){
        head = p;
    }
    else{
        head->next = p;
    }

}

Node* prob2(Battle* battles, int n){
    Node* head = nullptr;
    for(int i = 0; i < n; i++){
        addTail(head, battles[i]);
    }
}
int prob3(Node* head, string start_year, string end_year){
    int count = 0;
    int start;
    int end;
    start = stoi(start_year);
    end = stoi(end_year);
    for(Node*cur = head; cur!= nullptr; cur = cur->next){
        stringstream ss(cur->battle.from_date);
        string tmp;
        getline(ss, tmp, '-');
        getline(ss, tmp, '-');
        getline(ss, tmp);
        int start2 = stoi(tmp);
        if(start = start2){
            stringstream ss(cur->battle.to_date);
            string tmp;
            getline(ss, tmp, '-');
            getline(ss, tmp, '-');
            getline(ss, tmp);
            int end2 = stoi(tmp);
            if(end = end2){
                count++;
            }
        }
    }
}

void prob4(Node*& head, string general){
    for(int i = 0; i < head->battle.total_famous_generals; i++){
        if(head->battle.list_famous_generals[i] == general)
        Node* p = head;
        head = head->next;
        delete p;
        continue;
    }
    Node* cur = head;
    while(cur!=nullptr){
      for(int i = 0; i < cur->battle.total_famous_generals i++){
        if(cur->battle.list_famous_generals[i] == general){
        Node* p = cur;
        cur = cur->next;
        delete p;
        
        }
    cur = cur->next;
    }
}


int main(){
   

    return 0;
}