#include <iostream>
#include <sstream>
#include <string>
#include <vector>
#include <fstream>
using namespace std;
struct Date{
    int day, month, year;
    string era;
};
struct General{
    string name, nationality;
    Date born, death;
    vector<string> known_battles;
};
struct Node{
    General general;
    Node* left;
    Node* right;
};

Date parseDate(string dateStr){
    Date d;
    d.day = stoi(dateStr.substr(0, 2));
    d.month = stoi(dateStr.substr(3,2));
    int spacePos = dateStr.find(' ');
    d.year = stoi(dateStr.substr(6, spacePos - 1));
    d.era = dateStr.substr(spacePos + 1);
    return d;
}

vector<string> parseBattle(string battle){
    int cnt = 1;
    for(char c : battle){
        if( c == '|') cnt++;
    }
    stringstream ss(battle);
    vector<string> battles;
    string segment;
    for(int i = 0; i < cnt; i++){
    while(getline(ss, segment, '|')){
        segment.push_back(battles[i]);
    }}
    return battles;
}

vector<General> prob1(string filename){
    vector<General> res;
    ifstream fin(filename);
    if(!fin.is_open()) return;
    string val, line, header, tmp;
    getline(fin, header);
    General g;
    stringstream ss(line);
    while(getline(fin, line)){
        getline(ss, g.name, ',');
        getline(ss, g.nationality, ',');
        getline(ss, tmp, ',');
        g.born = parseDate(tmp);
        getline(ss, tmp, ',');
        g.death = parseDate(tmp);
        getline(ss, tmp);
        g.known_battles = parseBattle(tmp);
        res.push_back(g);
    }
    return res;
}
void create Node(General g){
    Node* tmp = new Node;
    tmp -> general = g;
    tmp -> left = tmp -> right = NULL;
    return tmp;
}

bool isOlder(Date a, Date b){
    if(a.era != b.era){
        return yearA == "BC";
    }
    if(a.year != b.year){
        return a.year < b.year;
    }
    if(a.month != b.month){
        return a.month < b.month;
    }
    return a.day < b.day;
}
// void insertNode(Node*& root, General g){
//     if(root == NULL) root = create(g);
//     if(isOlder(root -> g.born, root -> r -> g.born)){
//         root -> left = insertNode(root -> left, g);
//     }
//     else {
//         root -> right = insertNode(root -> right, g);
//     }
//     if(root -> g.born == root -> r -> g.born){
//         if(isOlder(root -> g.death, root -> r -> g.death)){
//             root -> left = insertNode(root -> left, g);
//         }
//         else{
//             root -> right = insertNode(root -> right, g)
//         }
//     }
// }
Node* prob2(vector<General> generals){

}