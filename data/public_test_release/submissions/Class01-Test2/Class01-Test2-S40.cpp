#include <iostream>
#include <vector>
#include <fstream>
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
vector<string> known_battles;
};

struct Node {
General general;
Node* left;
Node* right;
};

int prob3(Node* root, string born_year){
    if(root == NULL) return 0;
    
}



int main(){
    vector<General> a = prob1("abc.csv");
    cout << a[0].name;
}










vector<General> prob1(string filename){
    fstream file123(filename);
    if(!file123.is_open()){
        cout << "KHONG MO DUOC FILE";
        return {};
    }
    string line;
    getline(file123, line);
    General c;
    string day;
    vector<General> list;
    int i = 0;
    while(getline(file123, line)){
        stringstream ss(line);
        getline(ss, c.name, ',');
        getline(ss, c.nationality, ',');
        getline(ss, day,'-' );
        c.born.day = stoi(day);
        getline(ss, day,'-' );
        c.born.month = stoi(day);
        getline(ss, day,' ' );
        c.born.year = stoi(day);
        getline(ss, c.born.era,',');
        //death
        getline(ss, day,'-' );
        c.death.day = stoi(day);
        getline(ss, day,'-' );
        c.death.month = stoi(day);
        getline(ss, day,' ' );
        c.death.year = stoi(day);
        getline(ss, c.death.era,',');
        //known_battle
        getline(ss, c.known_battles[i],'|');
        i++;
        getline(ss, c.known_battles[i],'|');
        i++;
        getline(ss, c.known_battles[i],',');        
    }
    list.push_back(c);
    return list;
}