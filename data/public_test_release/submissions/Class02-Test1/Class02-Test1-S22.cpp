#include <iostream>
#include <sstream>
#include <fstream>
using namespace std;

struct Battle{
    string name, location;
    string from_date, to_date;
    int total_famous_generals;
    string* list_famous_generals;
};

Battle* prob1(string filename, int& n){
    ifstream fin(filename.c_str());

    if(!fin.is_open()){
        cout << "Error: Can not open file!";
        n = 0;
        return NULL;
    }

    n = 0;
    string line;
    while (getline(fin, line)){
       if(!line.empty()){
        n++;
       }
    }

    Battle* battles = new Battle[n];

    fin.clear();
    fin.seekg(0);

    int i{};
    while(getline(fin, line) && i < n){
        stringstream ss(line);
        string buffer;

        getline(ss, battles[i].name, ',');
        getline(ss, battles[i].location, ',');
        getline(ss, battles[i].from_date, ',');
        getline(ss, battles[i].to_date, ',');
        getline(ss, buffer, ',');
        getline(ss, buffer, ',');
        getline(ss, buffer);

        if(buffer.empty()){
            battles[i].total_famous_generals = 0;
            battles[i].list_famous_generals = NULL;
        }
    }
}

struct Node{
    Battle battle;
    Node* next;
};

Node* prob2(Battle* battles, int n){

}

int prob3(Node* head, string start_year, string end_year){

}

void prob4(Node*& head, string general){

}




