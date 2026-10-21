#include <iostream>
#include <fstream>
#include <vector>
#include <string>
#include <cstring>
#include <sstream>
#include <cmath>
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
    General g;
    ifstream fin(filename);
    if(!fin.is_open()){
        cout << "Error";
        return;
    }
    string tmp;
    string line;
    getline(fin, line);
    // while(getline(fin, g.name, ',')){
    //     int l = 0, r = 0;

    //     getline(fin, g.nationality, ',');
    //     getline(fin, tmp, '-');
    //     g.born.day = stoi(tmp);
    //     getline(fin, tmp, '-');
    //     g.born.month = stoi(tmp);
    //     getline(fin, tmp, ' ');
    //     g.born.year = stoi(tmp);
    //     getline(fin, g.born.era, ',');
    //     getline(fin, tmp, '-');
    //     g.death.day = stoi(tmp);
    //     getline(fin, tmp, '-');
    //     g.death.month = stoi(tmp);
    //     getline(fin, tmp, ' ');
    //     g.death.year = stoi(tmp);
    //     getline(fin, g.death.era, ',');

    //     r = 
    //     //getline(fin, tmp, ',');
    //     // for(int i = 0; i < tmp.size; i++)
    //     //     g.known_battles.at(i) = tmp[i];

        
    // }
    fin.close();

}