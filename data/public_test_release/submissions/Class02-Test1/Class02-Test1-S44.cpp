#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
#include <cstring>
#include <cmath>
using namespace std;
struct Battle{
    string BattleName, Location;
    string FromDate, ToDate;
    int TotalFamousGenerals;
    string* ListFamousGenerals;
};
struct Node {
    Battle battle;
    Node* next;
};
int counting(string filename) {
    int count=0;
    ifstream infile(filename);
    string line;
    getline(infile, line);
    while(getline(infile, line)){
        count++;
    }
    infile.close();
    return count;
}
Battle* prob1(string filename, int& n){
    int count
}

Node* prob2(Battle* battles, int n);

int prob3(Node* head, string start_year, string end_year);

void prob4(Node*& head, string general);