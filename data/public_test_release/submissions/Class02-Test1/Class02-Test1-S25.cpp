#include <iostream>
#include <string>
#include <fstream>
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

int countLine(string filename){
    ifstream fin(filename);
    string line="";
    getline(fin, line);
    int count=0;
    while(getline(fin, line)){
        if(!line.empty()){
            count++;
        }
    }
    fin.close();
    return count;
}

int TFG(string line){
    int count=0;
    for(int i=0; i<line.size(); i++){
        if(line[i]==';'){
            count++;
        }
    }
    return count+1;
}

Battle* prob1(string filename, int& n){
    ifstream fin(filename);
    string line = "";
    getline(fin, line);
    n=countLine(filename);
    Battle* arr = new Battle[n];
    Battle temp;
    int i=0;
    while(getline(fin, temp.name, ',')){
        getline(fin, temp.location, ',');
        getline(fin, temp.from_date, ',');
        getline(fin, temp.to_date, ',');
        getline(fin, line, ',');
        getline(fin, line, ',');
        getline(fin, line, ',');
        temp.total_famous_generals = TFG(line);
        temp.list_famous_generals = &line;
        arr[i]=temp;
        i++;
    }
    fin.close();
    return arr;
}

Node* creNode(Battle data){
    Node* p = new Node();
    p->next=NULL;
    p->battle=data;
    return p;
}

void addTail(Node*& head, Battle data){
    Node* p = creNode(data);
    if(head==NULL) head = p;
    Node* temp=head;
    while(temp->next!=NULL){
        temp=temp->next;
    }
    temp->next=p;
}

Node* prob2(Battle* battles, int n){
    Node* tmp = new Node();
    tmp = NULL;
    Battle* arr = battles;
    for(int i=0; i<n; i++){
        addTail(tmp, arr[i]);
    }
    return tmp;
}
int main(){
    int n=0;
    Battle* arr = prob1("50-european-battles-first-20.csv", n);
    cout << arr[0].list_famous_generals;
    return 0;
}