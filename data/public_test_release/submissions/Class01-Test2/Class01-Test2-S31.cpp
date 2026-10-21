#include <iostream>
#include <fstream>
#include <string>
#include <sstream>
#include <vector>
#include <cstring>
#include <cmath>
using namespace std;
struct Date{
    int day;
    int mounth;
    int year;
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

vector<string> ParseBattles(string a){
    vector<string> b;
    if (a.empty()) return b;

    string line;
    stringstream ss(a);
    while (getline(ss,line, '|'))
    {
        b.push_back(line);
    }
    return b;
}

vector<General> prob1(string filename){
    vector<General> g;
    fstream fin (filename);
    if (fin.fail()){
        cout << "Error opening file!" << endl;
        return g;
    }

    string line;
    getline(fin,line);

    while(getline(fin,line)){
        stringstream ss(line);
        string totalwar, strDay,strMounth,strYear, Battles;
        General A;

        getline (ss ,A.name, ',');
        getline (ss ,A.nationality, ',');
        //Parse Born data
        getline (ss ,strDay, '-');
        getline (ss ,strMounth, '-');
        getline (ss ,strYear, ' ');
        getline (ss ,A.born.era, ',');

        A.born.day = strDay.empty() ? 0 : stoi(strDay);
        A.born.mounth = strMounth.empty() ? 0 : stoi(strDay);
        A.born.year = strYear.empty() ? 0 : stoi(strDay);
        //Parse Death date
        getline (ss ,strDay, '-');
        getline (ss ,strMounth, '-');
        getline (ss ,strYear, ' ');
        getline (ss ,A.death.era, ',');

        A.death.day = strDay.empty() ? 0 : stoi(strDay);
        A.death.mounth = strMounth.empty() ? 0 : stoi(strDay);
        A.death.year = strYear.empty() ? 0 : stoi(strDay);

        getline(ss, Battles, ',');
        A.known_battles = ParseBattles(Battles);
        getline (ss, line,',');
        getline (ss, line,',');
        getline (ss, line,',');
        getline (ss, line);
        g.push_back(A);
    }

    return g;
}

bool CompareDate(General A, General B){
    if (A.born.era == "BC" && B.born.era == "AD") return true;
    if (A.born.era == B.born.era){
        if (A.born.year < B.born.year) return true;

        else if (A.born.year > B.born.year) return false;

        else{
                if (A.born.mounth < B.born.mounth) return true;
                else if (A.born.mounth > B.born.mounth) return false;
                else
                {
                    if (A.born.day < B.born.day) return true;
                    else if (A.born.day > B .born.day) return false;
                    else{
                        if (A.death.era == B.death.era){
                            if (A.death.year < B.death.year) return true;
                            else if (A.death.year > B.death.year) return false;
                            else{
                                if (A.death.mounth < B.death.mounth) return true;
                                else if (A.death.mounth > B.death.mounth) return false;
                                else{
                                    if (A.death.day < B.death.day) return true;
                                    else if (A.death.day > B.death.day) return false;
                                }
                            }
                        }
                    }
                }
            }       
    }   
    return false;
}

Node* CreateNode(General a){
    Node* NewNode = new Node;
    NewNode -> general = a;
    NewNode -> left = NewNode -> right = nullptr;
    return NewNode;
}

void Inser(Node* &pRoot, General A){
    if (pRoot == nullptr){
        pRoot = CreateNode(A);
        return;
    }

    if (CompareDate(pRoot ->general, A)){
        Inser(pRoot -> left, A);
    }
    else{
        Inser(pRoot -> right, A);
    }
}
Node* prob2(vector<General> generals){
    Node* Root = CreateNode(generals[0]);
    for(int i = 1; i < generals.size(); ++i){
        Inser(Root, generals[i]);
    }
    return Root;
}



