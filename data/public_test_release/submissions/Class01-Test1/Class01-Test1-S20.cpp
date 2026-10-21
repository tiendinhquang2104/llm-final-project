#include<iostream>
#include<fstream>
#include<sstream>
#include<string>
#include<cstring>
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

Node* pHead = NULL;

General* prob1(string filename, int& n){
    ifstream fin(filename);
    if(!fin.is_open()){
        cout << "Can not open file.";
        return;
    string tmp, line;
    size_t start = 0;
    size_t end;
    getline(fin, line);
    while(fin.eof()){
        General g;
        end = line.find(',', start);
        g.name = line.substr(start, end - start);

        start = end + 1;
        end = line.find(',', start);
        g.nationality = line.substr(start, end - start);
        
        start = end + 1;
        end = line.find('-', start);
        tmp = line.substr(start, end - start);
        g.born.day = stoi(tmp);
        
        start = end + 1;
        end = line.find('-', start);
        tmp = line.substr(start, end - start);
        g.born.month = stoi(tmp);
        
        start = end + 1;
        end = line.find(' ', start);
        tmp = line.substr(start, end - start);
        g.born.year = stoi(tmp);
        
        start = end + 1;
        end = line.find(',', start);
        g.born.era = line.substr(start, end - start);
        
        start = end + 1;
        end = line.find('-', start);
        tmp = line.substr(start, end - start);
        g.death.day = stoi(tmp);
        
        start = end + 1;
        end = line.find('-', start);
        tmp = line.substr(start, end - start);
        g.death.month = stoi(tmp);
        
        start = end + 1;
        end = line.find(' ', start);
        tmp = line.substr(start, end - start);
        g.death.year = stoi(tmp);
        
        start = end + 1;
        end = line.find(',', start);
        g.death.era = line.substr(start, end - start);
        int count = 0;
        // while(g){
        //     start = end + 1;
        //     end = line.find('|', start);
        //     g.known_battles = line.substr(start, end - start);
        //     count++;
        // }
        g.total_known_battles = count;

        Node* newNode = new Node;
        newNode->general = g;
        newNode->next = pHead;
        pHead = newNode;
    }
    fin.close();
}