#include <iostream>
#include <iomanip>
#include <fstream>
#include <vector>
#include <string>
#include <algorithm>
#include <sstream>
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
vector<General> prob1(string filename){
    vector<General> g;
    ifstream fin(filename);
    if(fin.is_open()){
        string line;
        getline(fin, line);
        while(getline(fin, line)){
            stringstream ss(line);
            string word;
            vector<string> v;
            while(getline(ss, word, ',')){
                v.push_back(word);
            }
            General gen;
            gen.name = v[0];
            gen.nationality = v[1];
            vector<string> knowbattle;
            string s = v[4];
            stringstream ss1(s);
            string cell;
            while(getline(ss1, cell, '|')){
                knowbattle.push_back(cell);
            }
            gen.known_battles = knowbattle;
            string born = v[2].substr(0, 11);
            string eras = v[2].substr(11, 2);
            stringstream ss2(born);
            string kytu;
            vector<string> bo;
            while(getline(ss2, kytu, '-')){
                bo.push_back(kytu);
            }
            Date bornn;
            bornn.day = stoi(bo[0]);
            bornn.month = stoi(bo[1]);
            bornn.year = stoi(bo[2]);
            bornn.era = eras;
            gen.born = bornn;
            string death = v[3].substr(0, 11);
            string eras1 = v[3].substr(11, 2);
            stringstream ss3(death);
            string kytu1;
            vector<string> de;
            while(getline(ss3, kytu1, '-')){
                de.push_back(kytu1);
            }
            Date deathh;
            deathh.day = stoi(de[0]);
            deathh.month = stoi(de[1]);
            deathh.year = stoi(de[2]);
            deathh.era = eras1;
            gen.death = deathh;
            g.push_back(gen);
        }
        
    }
    return g;

}
struct Node {
    General general;
    Node* left;
    Node* right;
};
Node* CreateNode(General g){
    Node* newNode = new Node();
    newNode->general.born = g.born;
    newNode->general.death = g.death;
    newNode->general.name = g.name;
    newNode->general.nationality = g.nationality;
    newNode->general.known_battles = g.known_battles;
    return newNode;
}
bool cmp(General born, General born1){
    if(born.born.year != born1.death.year){
        return born.born.year < born1.born.year;
    }
    else{
        if(born.born.month != born1.born.month){
            return born.born.month < born1.born.month;
        }
    }
    return born.born.day < born1.born.day;
}
void InsertBST(Node* &pRoot, General gen){
    if(pRoot == nullptr){
        pRoot = CreateNode(gen);
        return;
    }
    else{
        if(cmp(gen, pRoot->general)){
            InsertBST(pRoot->left, gen);
        }
        else if(cmp(pRoot->general, gen)){
            InsertBST(pRoot->right, gen);
        }
    }
}
Node* prob2(vector<General> generals){
    Node* pRoot = nullptr;
    for(int i = 0; i < generals.size(); i++){
        InsertBST(pRoot, generals[i]);
    }
    return pRoot;
}

int prob3(Node* root, string born_year){
    int cnt = 0;
    if(root == nullptr){
        return;
    }
    string s = to_string(root->general.born.year) + " " + root->general.born.era;
    if(s == born_year){
        cnt++;
    }
    prob3(root->left, born_year);
    prob3(root->right, born_year);
    return cnt;
}

