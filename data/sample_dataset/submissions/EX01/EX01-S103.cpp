#include <iostream>
#include <string.h>
#include <fstream>
#include <cstring>
#include "50-best-european-generals-cleaned-first-20.csv"

using namespace std;

struct Date {
    int day, month, year;
    string era; // AD or BC
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
}
Node* createNode(Node* node, int data){

}
Node* createGeneral(General* gr){
    Node* p =  new Node;
    p->general = gr;
    g->next = nullptr;
}
General* prob1(string filename, int& n){
    fstream file("50-best-european-generals-cleaned-first-20.csv");
    file.open("50-best-european-generals-cleaned-first-20.csv");
    if (file.open()){
        for (int i = 0; i < n; i++){
            file << file[i];
            

        }
    }
    file.close();
    return nullptr;
    
}

int main(){
    string file = "50-best-european-generals-cleaned-first-20.csv";
    General* prob1(file, 20);
}