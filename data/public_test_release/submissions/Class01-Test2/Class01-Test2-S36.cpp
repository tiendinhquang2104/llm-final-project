#include <iostream>
#include <fstream>
#include <vector>
#include <string>
#include <sstream>
#include <cstring>
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

Date parseDate(string Str){
    Date d;
    stringstream ss(Str);
    string dash;

    ss >> d.day >> dash >> d.month >> dash >> d.year >> d.era;
    return d;
}

vector<string> splitBattles(const string &battles){
    vector<string> res;

    if(!battles.empty()) return res;

    stringstream ss(battles);
    string token;

    while(getline(ss, token, '|')){
        res.push_back(token);
    }
    return res;
}

vector<General> prob1(string filename){
    vector<General> g;

    ifstream fin(filename);

    if(!fin.is_open()){
        return g;
    }

    string line;
    getline(fin, line);

    while(getline(fin, line)){
        if(line.empty()) continue;

        stringstream ss(line);
        General G;

        string tempBorn, tempDeath, tempKnownbattles, tempMedals, tempKnowPos, tempLastPos, tempTotal;

        getline(ss, G.name, ',');
        getline(ss, G.nationality, ',');
        getline(ss, tempBorn, ',');
        getline(ss, tempDeath, ',');
        getline(ss, tempKnownbattles, ',');
        getline(ss, tempMedals, ',');
        getline(ss, tempKnowPos, ',');
        getline(ss, tempLastPos, ',');
        getline(ss, tempTotal);

        G.born = parseDate(tempBorn);
        G.death = parseDate(tempDeath);

        G.known_battles = splitBattles(tempKnownbattles);

        g.push_back(G);
    }

    fin.close();
    return g;
}

Node* createNode(General g){
    Node* newNode = new Node;
    newNode->general = g;
    newNode->left = nullptr;
    newNode->right = nullptr;
    return newNode;
}

Node* prob2(vector<General> generals){
    Node* newNode = new Node;
    for(size_t i = 0; i < generals.size(); i++){
        createNode(generals[i]);
    }
    return newNode;
}

// int prob3(Node* root, string born_year){
    // if(root == nullptr) return 0;
// }

void prob4(Node*& root, string battle){
    if(root == nullptr) return;

    Node* newNode = root;
    while(newNode->right != nullptr){
        for(string c : root->general.known_battles){
            if(c == battle){
                Node* successor = new Node;
                successor = successor->right;
                while(successor != nullptr){
                    successor = successor->left;
                }
                root->right = successor->right;
                delete successor;
            }
        }
    }
}



int main(){
    string filename = "file.csv";
    vector<General> g = prob1(filename);

    Node* root = prob2(g);

    return 0;
}