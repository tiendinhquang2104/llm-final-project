#include <iostream>
#include <string>
#include <fstream>
#include <sstream>
#include <cstring>
using namespace std;

struct Battle {
    string name;
    string location;
    string from_date;
    string to_date;
    int total_famous_generals;
    string* list_famous_generals;
};

int countLine(string filename){
    fstream fin(filename);
    int dem = 0;
    string line;

    getline(fin,line);

    while (getline(fin, line)){
        dem++;
    }

    fin.close();
    return dem;
}

struct Node{
    Battle battle;
    Node* next;
};


Battle* pro1(string filename, int& n){
    string line;
    Battle p;
    stringstream ss(line);
    string temp;

    getline(ss, p.name, ',');
    getline(ss, p.location,',');
    getline(ss, p.from_date, ',');
    getline(ss, p.to_date, ',');
    getline(ss, temp, ',');
    getline(ss, temp,',');
    getline(ss, temp);
    
    string *a = p.list_famous_generals;
    *a = temp;
    int count = 0;
    while (getline(ss, temp, ';')){
        count++;
    }
    cout << count;

}
