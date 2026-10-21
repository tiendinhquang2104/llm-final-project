#include<iostream>
#include<fstream>
#include<cstring>
#include<string>
using namespace std;
struct Date {
int day, month, year;
string era; 
};
struct General {
string name, nationality;
Date born, death;
int total_known_battles;
string* known_battles;
};
struct Node {
General general;
Node* next;
};
int countline(string filename){
    ifstream fin(filename);
    string line;
    getline(fin, line, '\n');
    int n = 0;
    while(getline(fin, line, '\n')){
        getline(fin, line, '\n');
        n++;
    }
    fin.close();
    return n;
}
General* prob1(string filename, int& n){
    n = countline(filename);
    General* a = new General[n];
    fstream fin(filename);
    getline(fin, line);
    for(int i = 0; i < n; i++){
        getline(fin, line);
        n++;
    }
    fin.close();
    return 

}

