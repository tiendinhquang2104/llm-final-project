#include <iostream>
#include <fstream>
#include <sstream>
#include <cmath>
#include <cstring>

using namespace std;

struct Date {
    int day, month, year;
    string era;
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

General* prob1(string filename, int& n) {
    fstream file(filename);
    if(!file.is_open()) {
        return;
    }
    string born;
    stringstream ss;
    string line;
    getline(ss, line); // Ignore 1st line
    while(file) {
        Date date;
        General general;
        getline(ss, general.name, ',');
        getline(ss, general.nationality, ',');

        getline(ss, to_string(general.born.month), '-');
        getline(ss, to_string(general.born.day), '-');
        getline(ss, to_string(general.born.year), ' ');
        
        string temp1;
        temp1 = stoi(date.era);
        getline(ss, temp1, ',');

        getline(ss, to_string(general.death.month), '-');
        getline(ss, to_string(general.death.day), '-');
        getline(ss, to_string(general.death.year), ' ');
        
        string temp2;
        temp2 = stoi(date.era);
        getline(ss, temp1, ',');
        getline(ss, to_string(general.total_known_battles), ',');
    }
}

Node* prob2(General* generals, int n) {
    Node* head = NULL;
    Node* tail = NULL;
    string filename;
    fstream file(filename);
    stringstream ss;

    if(!file.is_open())   return;
    while(file) {
        General general;
        Date date;
        getline(ss, general.name, ',');
        getline(ss, general.nationality, ',');

        getline(ss, to_string(general.born.month), '-');
        getline(ss, to_string(general.born.day), '-');
        getline(ss, to_string(general.born.year), ' ');
        
        string temp1;
        temp1 = stoi(date.era);
        getline(ss, temp1, ',');

        getline(ss, to_string(general.death.month), '-');
        getline(ss, to_string(general.death.day), '-');
        getline(ss, to_string(general.death.year), ' ');
        
        string temp2;
        temp2 = stoi(date.era);
        getline(ss, temp1, ',');
        getline(ss, to_string(general.total_known_battles), ',');
        
    }
}

General prob3(Node* head){
    Node* curr = head;
}

void prob4(Node*& head, string nationality) {

}
