#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>
using namespace std;
struct Date {
int day, month, year;
string era; // AD or BC
};
// struct Node {
// General general;
// Node* left;
// Node* right;
// };
struct General {
string name, nationality;
Date born, death;
vector<string> known_battles;
};
Date parseDate(const string& s){
    Date d = {0, 0, 0, "AD"};
    if(s.empty()) return d;
    d.day = stoi(s.substr(0,2));
    d.month = stoi(s.substr(3,2));
    int spacePos = s.find(' ');
    d.year = stoi(s.substr(6,spacePos- 6));
    d.era = s.substr(spacePos + 1);
    return d;
}
vector<string> parsebattles(General &g, const string &s){
    vector<string> temp;
    string token;
    istringstream ss(s);
    int cnt = 1;
    for(char c : s) if(c == '|') cnt++;
    while(getline(ss, token, '|')){
        temp.push_back(token);
    }
    return temp;
}
vector<General> prob1(string filename){
    vector<General> arr;
    ifstream fin(filename);
    if(!fin.is_open()) return arr;
    string line;
    getline(fin, line);
    while(getline(fin, line)){
        string token;
        istringstream ss(line);
        General g;
        getline(ss, g.name, ',');
        getline(ss, g.nationality, ',');
        getline(ss, token, ',');
        g.born = parseDate(token);
        getline(ss, token, ',');
        g.death = parseDate(token);
        getline(ss, token, ',');
        g.known_battles = parsebattles(g, token);
        arr.push_back(g);
    }
    fin.close();
    return arr;
}
// bool isOlder(Date a, Date b){
//     int yearA = (a.era == "BC") ? -a.year : a.year;
//     int yearB = (b.era == "BC") ? -b.year : b.year;
//     if(yearA != yearB) return yearA < yearB;
//     if(a.month != b.month) return a.month < b.month;
//     return a.day < b.day;
// }
// Node* createNode(General g){
//     Node* cur = new Node;
//     cur -> general = g;
//     cur -> left = cur -> right = nullptr;
//     return cur;
// }
// Node* Insert(Node* pRoot, General g){
//     if(!pRoot){
//         return createNode(g);
//     }
//     if(isOlder(pRoot->general.born, g.born)){
//         pRoot -> left = Insert(pRoot -> left, g);
//     }
//     if(!isOlder(pRoot -> general.born, g.born)){
//         pRoot -> right = Insert(pRoot -> right, g);
//     }
//     return pRoot;
// }
// Node* prob2(vector<General> generals){
//     Node* pRoot = nullptr;

// }
int main(){
    return 0;
}