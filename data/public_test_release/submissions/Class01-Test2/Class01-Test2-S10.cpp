#include<iostream>
#include<fstream>
#include<vector>
#include<sstream>
#include<string>
#include<cstring>
using namespace std;
struct Date {
int day, month, year;
string era; // AD or BC
};
struct General {
string name, nationality;
Date born, death;
vector<string> known_battles;
};
struct Node {
General general;
Node* left;
Node* right;
};
Date parseDate(const string & date) {
    Date d;
    stringstream ss(date);
    char dash;
    ss >> d.day >> dash >> d.month >> dash >> d.year >> d.era;
    return d;
}
vector <string> splitBattles(const string &battle) {
    vector<string> res;
    if(battle.empty()) return res;
    stringstream ss(battle);
    string token;
    while(getline(ss, token, '|')){
        res.push_back(token);
    }
    return res;
}
vector<General> prob1(string filename) {
   vector<General> data;
    ifstream fin(filename);
    if(!fin.is_open()) return data;
    string header;
    getline(fin, header);
    string line;
    while(getline(fin,line)) {
        string token;
        General g;
        stringstream ss(line);
        getline(ss, g.name, ',');
        getline(ss, g.nationality, ',');
        getline(ss, token, ',');
        g.born = parseDate(token);
        getline(ss, token, ',');
        g.death = parseDate(token);
        getline(ss, token, ',');
        g.known_battles = splitBattles(token);
        getline(ss, token, ',');
        getline(ss, token, ',');
        getline(ss, token, ',');
        getline(ss, token);
        data.push_back(g);
    }
    fin.close();
    return data;
}
bool checkAge(General x, General y) {
    if(x.born.era == "BC") x.born.year = -x.born.year;
    if(y.born.era == "BC") y.born.year = -y.born.year;
    if(x.born.year < y.born.year) return true;
    else if(x.born.year == y.born.year && x.born.month < y.born.month) return true;
    else if(x.born.year == y.born.year && x.born.month == y.born.month && x.born.day < y.born.day) return true;
    else {
        if(x.born.year == y.born.year && x.born.month == y.born.month && x.born.day == y.born.day){
            if(x.death.era == "BC") x.death.year = -x.death.year;
            if(y.death.era == "BC") y.death.year = -y.death.year;
            if(x.death.year < y.death.year) return true;
            else if(x.death.year == y.death.year && x.death.month < y.death.month) return true;
            else if(x.death.year == y.death.year && x.death.month == y.death.month && x.death.day < y.death.day) return true;
        }
    }
    return false;
}
Node*CreateNode(General x) {
   Node * newnode = new Node;
    newnode->general = x;
    newnode->left = newnode->right = nullptr;
}
Node * Insert(Node * pRoot, General x) {
    if(pRoot == nullptr) {
        pRoot = CreateNode(x);
        return pRoot;
    }
    else if(checkAge(x, pRoot->general)) pRoot->left = Insert(pRoot->left, x);
    else if(checkAge(pRoot->general, x)) pRoot->right = Insert(pRoot->right, x);
    return pRoot;
}
Node* prob2(vector<General> generals) {
    Node * pRoot = nullptr;
    for(auto &g : generals) {
        pRoot = Insert(pRoot, g);
    }
    return pRoot;
}
Date parseString(const string &s) {
    Date a;
    stringstream ss(s);
    ss >> a.year >> a.era;
    return a;
}
int prob3(Node* root, string born_year) {
    if(root == nullptr) return 0;
    Date a = parseString(born_year);
    if(root->general.born.year == a.year && root->general.born.era == a.era) {
        return 1 + prob3(root->left, born_year) + prob3(root->right, born_year);
    }
    else
        return prob3(root->left, born_year) + prob3(root->right, born_year);
}
Node * findmin (Node * pRoot){
    if(pRoot->left == nullptr) return pRoot;
    else
        return pRoot->left = findmin(pRoot->left);
}
Node * Remove(Node * &pRoot, General x) {
            if(pRoot->left == nullptr && pRoot->right == nullptr) {
                delete pRoot;
                pRoot = nullptr;
            }
            else if(pRoot->left != nullptr && pRoot->right == nullptr) {
                Node * temp = pRoot;
                pRoot = pRoot->left;
                delete temp;
            }
            else if(pRoot->right != nullptr && pRoot->left == nullptr) {
                Node * temp = pRoot;
                pRoot = pRoot->right;
                delete temp;
            }
            else {
               Node * temp = findmin(pRoot->right);
               pRoot->general = temp->general;
               pRoot->right = Remove(pRoot->right, temp->general);
            }
        return pRoot;
    }
void prob4(Node*& root, string battle) {
    if(root == nullptr) return;
    int size = root->general.known_battles.size();
    for(int i = 0; i < size; i++) {
        if(root->general.known_battles[i] == battle) {
            root = Remove(root, root->general);
        }
    }
    prob4(root->left, battle);
    prob4(root->right, battle);
}