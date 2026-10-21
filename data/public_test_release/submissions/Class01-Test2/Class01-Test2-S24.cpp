#include <iostream>
#include <vector>
#include <queue>
#include <cstring>
#include <fstream>
#include <sstream>
#include <string>
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
vector<General> prob1(string filename)
{
    vector<General> G;
    fstream fin;
    fin.open(filename);
    if(!fin.is_open())
        return G;
    string ignore_line;
    getline(fin, ignore_line, '\n');
    string line = "";
    while(getline(fin, line))
    {
        General A;
        string battle = "";
        string tmp = "";
        stringstream ss(line);
        getline(ss, A.name, ',');
        getline(ss, A.nationality, ',');
        try {
        getline(ss, tmp, '-'); A.born.day = stoi(tmp);
        getline(ss, tmp, '-'); A.born.month = stoi(tmp);
        getline(ss, tmp, ' '); A.born.year = stoi(tmp);
        getline(ss, A.born.era, ',');}
        catch (...){
        A.born.day = 0;
        A.born.month = 0;
        A.born.year = 0; }

        try {
        getline(ss, tmp, '-'); A.death.day = stoi(tmp);
        getline(ss, tmp, '-'); A.death.month = stoi(tmp);
        getline(ss, tmp, ' '); A.death.year = stoi(tmp);
        getline(ss, A.death.era, ',');}
        catch (...){
        A.death.day = 0;
        A.death.month = 0;
        A.death.year = 0; }

        getline(ss, battle, ',');
        A.known_battles.push_back(battle);
        G.push_back(A);
        getline(fin, line, '\n');
    }
    fin.close();
    return G;
}
void Insert(Node* &pRoot, General G)
{

    if(pRoot == NULL){
        pRoot->general = G;
        return; }
    if(pRoot->general.born.year > G.born.year)
        Insert(pRoot->right, G);
    else if(pRoot->general.born.year < G.born.year)
        Insert(pRoot->left, G);
    else if(pRoot->general.born.year == G.born.year &&  pRoot->general.born.month > G.born.month)
        Insert(pRoot->right, G);
    else if(pRoot->general.born.year == G.born.year &&  pRoot->general.born.month < G.born.month)
        Insert(pRoot->left, G);
    else if(pRoot->general.born.year == G.born.year && pRoot->general.born.month == G.born.month || pRoot->general.death.year > G.death.year)
        Insert(pRoot->right, G);
    else if(pRoot->general.born.year == G.born.year && pRoot->general.born.month == G.born.month || pRoot->general.death.year < G.death.year)
        Insert(pRoot->left, G);
}
Node* prob2(vector<General> generals)
{
    Node* pRoot = NULL;
    for(int i = 0; i < generals.size(); i++)
        Insert(pRoot, generals[i]);
    return pRoot;
}
int main()
{
    string filename = "D:\00000000\50-best-european-generals-cleaned-first-20.txt";
    vector<General> VecG = prob1(filename);
    cout<<VecG.size();

    return 0;
}
