#include<iostream>
#include<fstream>
#include<string>
#include<sstream>
#include<cmath>
using namespace std;

struct Date {
int day, month, year;
string era; // AD or BC
};

struct General {
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
    fstream f(filename);
    General* skibi = new General[n];
    if(!f.is_open()){
        cout << "file cannot read";
        return;
    }
    string line;
    int i = 0;
    while(getline(f, line)){
        skibi[i].name = getline(f, line, ';');
        skibi[i].nationality = getline(f, line, ';');
        skibi[i].born.day = stoi(getline(f, line, ';'));
        skibi[i].born.month = stoi(getline(f, line, ';'));
        skibi[i].born.year = stoi(getline(f, line, ';'));
        skibi[i].born.era =getline(f, line, ';');
        skibi[i].death.day = stoi(getline(f, line, ';'));
        skibi[i].death.month = stoi(getline(f, line, ';'));
        skibi[i].death.year = stoi(getline(f, line, ';'));
        skibi[i].death.era = getline(f, line, ';');
        skibi[i].total_known_battles = stoi(getline(f, line, ';'));
        skibi[i].known_battles = getline(f, line, ';');
        i++;
    }
    return skibi;
}
Node* prob2(General* generals, int n){
    Node* newem = new Node;
    newem->general = generals[0];
    newem->next = nullptr;
    Node* current = newem;
    for(int j = 1; j < n; j++){
        Node* newem1= new Node;
        newem1-> next = nullptr;
        newem1->general = generals[j];
        current->next= newem1;
        current = current ->next;
    }
return newem;
}
General prob3(Node* head){
    Node* current = head;
    while(current->next != nullptr){
        if(current->general.born.era == "BC")
    }
}