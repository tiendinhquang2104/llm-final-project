#include <iostream>
#include <fstream>
#include <string>
#include <cstring>
#include <sstream>

using namespace std;

struct Battle {
string name, location;
string from_date, to_date;
int total_famous_generals;
string* list_famous_generals;
string result;
};

struct Node {
Battle battle;
Node* next;
};

int countLine(string filename){
    ifstream fin;
    string line;
    int count = 0;

    fin.open(filename);
    getline(fin, line, "\n");
    while(getline(fin, line, "\n")){
        count += 1;
    }
    fin.close(filename);
    return count;
}
Battle* prob1(string filename, int& n){
    ifstream fin;
    fin.open(filename);

    n = countLine(filename);
    Battle* result = new Battle(n);
    string line;

    getline(fin, line, "\n");
    Battle tmp;
    while(getline(fin, line, "\n")){
        tmp.name = line;

        getline(fin, line, "\n");
        tmp.location = line;

        getline(fin, line, "\n");
        tmp.from_date = line;

        getline(fin, line, "\n");
        tmp.to_date = line;

        getline(fin, line, "\n");
        tmp.total_famous_generals = line;
    }
    fin.close();
    return result;
};
