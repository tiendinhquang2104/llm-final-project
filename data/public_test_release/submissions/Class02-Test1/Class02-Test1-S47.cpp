#include <iostream>
#include <fstream>
#include <string>
#include <sstream>
#include <cstring>
using namespace std;

struct Battle {
string name, location;
string from_date, to_date;
int total_famous_generals;
string* list_famous_generals;
};

struct Date{
    int day, month, year;
};

int parseDate(string s){
    Date d;

}

int splitData(string filename, string s){
    ifstream fin(filename); 
    string line;
    int tmp;


    fin.close();
    return tmp;

}

Battle* prob1(string filename, int& n){
    ifstream fin(filename);
    string line;

    getline(fin, line);
    while(getline(fin, line)){
        
    };

    fin.close();
   return 0;
}

struct Node {
Battle battle;
Node* next;
};

struct List{
    Node* head;
    Node* tail;
};

Node* prob2(Battle* battles, int n){

}

int prob3(Node* head, string start_year, string end_year){

}

void prob4(Node*& head, string general){

}



int main(){

    
    return 0;
}

