#include <iostream>
#include <sstream>
#include <string>
#include <vector>
#include <fstream>
#include <cstring>
#include <cmath>
using namespace std;
struct Node {
General general;
Node* left;
Node* right;
};
struct Date {
int day, month, year;
string era; // AD or BC
};
struct General {
string name, nationality;
Date born, death;
vector<string> known_battles;
};
Date parseDate(const string& s){
    Date d;
    d.day = stoi(s.substr(0,2));
    d.month = stoi(s.substr(3,2));
    d.year = stoi(s.substr(6,4));
    d.era = s.substr(11);
    return d;
}
int getcount(const string&s){
    int count = 1;
    for ( char c:s){
        if(c == '|'){
            count++;
        }
    }
    return count;
}
vector<string> parsebattle(const string& s){
    int count = getcount(s);
    vector<string> battle;
    stringstream ss(s);
    string token;
    int i = 0;
    while(getline(ss,token,'|')){
        battle.push_back(token);
    }
    return battle;
}
vector<General> prob1(string filename){
    vector<General> result;
    ifstream fin(filename);
    if(!fin.is_open()){
        cout << " Khong mo duoc file";
        return;
    }
    string val,line,header,tmp;
    getline(fin,header);
    General g;
    stringstream ss(line);
    while(getline(fin,line)){
        getline(ss,g.name,',');
        getline(ss,g.nationality,',');
        getline(ss,tmp,',');
        g.born = parseDate(tmp);
        getline(ss,tmp,',');
        g.death = parseDate(tmp);
        getline(ss,tmp,',');
        g.known_battles = parsebattle(tmp);
        result.push_back(g);
    }
    fin.close();
    return result;
}
Node* createNode(General g){
    Node*p = new Node;
    p->general = g;
    p->left = NULL;
    p->right = NULL;
    return p;
}
bool Isolder(Date a, Date b){
    int yearA = a.year;
    if(a.era == "BC") yearA = -yearA;
    int yearB = b.year;
    if(b.era == "BC") yearB = -yearB;
    if(a.era == b.era) return yearA>yearB;
    if(yearA==yearB) return a.month > b.month;
    if(a.month == b.month ) return a.day > b.day;
}
Node* Insert(Node* pRoot,General g){
    if(pRoot == NULL){
        pRoot = createNode(g);

    }
    if(Isolder(pRoot->general.born,g.born)) Insert(pRoot->right,g);
    if(!Isolder(pRoot->general.born,g.born)) Insert(pRoot->left,g);
}
Node* prob2(vector<General> generals){
    Node* pRoot = NULL;
    for ( int i = 0; i<generals.size();i++){
        Insert(pRoot,generals[i]);
    }
    return pRoot;
}