#include <iostream>
#include <fstream>
#include <string>
using namespace std;

struct Date {
int day, month, year;
string era; // AD or BC
};
struct General {
string name, nationality, medal, knownPos, lastPos;
Date born, death;
int total_known_battles;
string* known_battles;
};

Date seprdate(string day){
    Date d = {0, 0, 0, ""};
    if(day.length() < 5 || day == "None") return d;
    int pos1 = day.find('-');
    int pos2 = day.find('-', pos1 + 1);
    int posSpace = day.find( ' ', pos2 + 1);
    int p1 = stoi(day.substr(0, pos1));
    int p2 = stoi(day.substr(pos1 + 1, pos2 - pos1 - 1));
    d.year = stoi(day.substr(pos2 + 1, posSpace - pos2 - 1));
    d.era = day.substr(posSpace + 1);
    if(p1 > 12){
    d.day = p1;
    d.month = p2;
    } else{
        d.month = p2;
        d.day = p1;
    }
    return d;
}

int countline(string filename){
    ifstream fin(filename);
    int cnt = 0;
    if(!fin.is_open()) return 0;
    string line;
    getline(fin, line);
    while(getline(fin, line)){
        if(!line.empty()) cnt++;
    }
    return cnt;
}

void splitBattle(General& g, string battles){
    int start = 0;
    int end = battles.find('|');
    int index = 0;
    int cnt = 1;
    for(char c : battles){
        if(c == '|') cnt++;
    }
    g.known_battles = new string[cnt];
    while(end != string::npos){
        g.known_battles[index++] = battles.substr(0, end - start);
        start = end + 1;
        end = battles.find('|', start + 1);
    }
    g.known_battles[index] = battles.substr(start, end);
}

General* prob1(string filename, int& n){
    ifstream fin(filename);
    if(!fin.is_open()) return;
    string line, bStr, dStr, wonBattle, battles;
    int n = countline(filename);
    General* g = new General[n];
    getline(fin, line);
    int i = 0;
    while(i < n && !fin.eof()){
        getline(fin, g[i].name, ',');
        getline(fin, g[i].nationality, ',');
        getline(fin, bStr, ',');
        getline(fin, dStr, ',');
        getline(fin, battles, ',');
        splitBattle(g[i], battles);
        getline(fin, g[i].medal, ',');
        getline(fin, g[i].knownPos, ',');
        getline(fin, g[i].lastPos, ',');
        getline(fin, wonBattle);
        g[i].born = seprdate(bStr);
        g[i].death = seprdate(dStr);
        g[i].total_known_battles = stoi(wonBattle);
        i++;
    }
    fin.close();
    return g;
}
// struct Node{
//     General general;
//     Node* next;
// };
// Node* makeNode(General g){
//     Node* a = new Node;
//     a->general = g;
//     a->next = NULL;
//     return a;
// }
// void addTail(Node* &head, General g){
//     Node* a = makeNode(g);
//     if(a == NULL){
//         a = head;
//         return;
//     }
//     Node* tmp = head;
//     while(tmp->next != NULL){
//         tmp = tmp->next;
//     }
//     tmp->next = a;
// }
// // Node* prob2(General* generals, int n){
// //     string filename;
// //     ifstream fin(filename);
// //     generals = prob1(filename, n);
// // }

int main(){

}