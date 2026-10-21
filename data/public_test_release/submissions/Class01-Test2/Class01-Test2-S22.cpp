#include<iostream>
#include<fstream>
#include<vector>
#include<string>
#include<algorithm>
using namespace std;
struct Date {
int day, month, year;
string era; 
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
vector<General> prob1(string filename){
    ifstream file(filename);
    if(!file.is_open()){
        cout << "Khong mo duoc file" << endl;
        return;
    }
    //getline(file, line);
    //while(getline(file, line)){
    //    string line, word;


    //}
    file.close();
}
/*Node* createNode(General g){
    Node*newNode = new Node;
    Node*left = NULL;
    Node* right = NULL;
    Node. general -> data = g;
    return newNode;

}/**/