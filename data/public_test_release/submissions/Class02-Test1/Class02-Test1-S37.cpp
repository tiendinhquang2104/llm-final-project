#include <iostream>
#include <fstream>
#include <string>
#include <sstream>
#include <cstring>
#include <cmath>
using namespace std;
struct Battle{
    string name, location;
    string from_date, to_date;
    int *total_famous_generals;
    string* list_famous_generals;
};
struct Node{
    Battle battle;
    Node* next;
};
Battle* prob1(string filename, int &n){
    cin >> n;
    Battle* prob1 = new Battle[n];
    ifstream fin("battles.csv");
    string str;
    stringstream ss;
    string line;
    for(int i =0; i < n; i++){
        getline(ss, line, ' ');
        prob1[i].name = line;
        prob1[i].location = line;
        prob1[i].from_date = line;
        prob1[i].to_date = line;
        prob1[i].total_famous_generals = &line;
        prob1[i].list_famous_generals = &line;
    }
    delete[] prob1;
    return prob1;
    
}
Node* prob2(Battle* battles, int n){
    return 0;
}
int prob3(Node* head, string start_year, string end_year){
    return 0;
}
void prob4(Node*& head, string general){

}
