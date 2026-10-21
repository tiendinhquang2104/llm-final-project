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
    ifstream file(filename);
    if(!file.is_open())
    {
        cout << "Ko mo duoc file";
    }
    string line;
    vector<General> g;
    getline(file, line);
    while(getline(file,line))
    {
        stringstream ss(line);
        string cell;
        General temp;
        vector<string> row;
        while(getline(ss,cell,","))
        {
            row.push_back(cell);
        }   
    }
    return g;

}
