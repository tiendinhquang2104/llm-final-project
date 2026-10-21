#include <iostream>
#include <string>
#include <fstream>
#include <sstream>
#include <cstring>
#include <cmath>
using namespace std;

struct Battle{
    string name,location;
    string from_date, to_date;
    int total_famous_generals;
    string* list_famous_generals;
};
struct Node{
    Battle battle;
    Node* next;
};
Battle* prob1(string filename,int &n){
    Battle prob1;
    ifstream fin("battles.csv");
    string st;
    fin >> st;
    getline(fin,st,'\n');
    fin.close();
    fin >> prob1.name >> prob1.location >> prob1.from_date >> prob1.to_date >> prob1.total_famous_generals;
};
Node* prob2(Battle* battles,int &n){

};
int prob3(Node* head,string start_year,string end_year){
    int count;
    return count;
};
void prob4(Node*& Head){

};


int main(){
    ifstream fin("battles.csv");
    string line;
    while(getline(fin,line,'\n')){
        cout << line <<endl;
    };
    return 0;
}