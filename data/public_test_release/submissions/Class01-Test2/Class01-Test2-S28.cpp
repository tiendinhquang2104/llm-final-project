#include<iostream>
#include<fstream>
#include<string>
#include<vector>
using namespace std;

struct Date{
    int dat, month, year;
    string era;
};
struct General{
    string name, nationality;
    Date born, death;
    vector<string> known_battles;
};
struct Node{
General general;
Node* left;
Node* right;
};

vector<General> prob1(string filename){
    ifstream fin(filename);
    if(!fin.is_open()){
        cout << "File not found" <<endl;
    }else{
    General temp;
    while(){

    }
   

    }
}
