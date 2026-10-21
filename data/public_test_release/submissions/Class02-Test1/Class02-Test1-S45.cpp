#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
using namespace std;

struct Battle {
string name, location;
string from_date, to_date;
int total_famous_generals;
string* list_famous_generals;
};


struct Node {
Battle battle;
Node* next;
};


int main() {
    ifstream File("50-european-battles-first-20.csv");

    string header;
    getline(File, header);
    Node* head = nullptr; Node* tail = nullptr;

    string line;
    Battle* prob1(string File, int& n){
    int i = 0;
    if(i<n) {
        Node* newnode = new Node;
        getline(File,line);
        stringstream ss(line);
        string temp;
        getline(line,temp,','); newnode->name = (temp);
        getline(line,temp,','); newnode->location = (temp);
        getline(line,temp,','); newnode->from_date = (temp);
        getline(line,temp,','); newnode->to_date = (temp);
        getline(line,temp,','); newnode->total_famous_generals = (temp);
        getline(line,temp,','); newnode->list_famous_generals = (temp);
        i++;
        if(head == nullptr) {
            head = tail = newnode;
        } else {
            tail->next = newnode;
            tail = newnode;
        }
         cout << newnode->name << newnode->location << newnode->form_date << newnode->to_date << newnode->total_famous_generals << newnode->list_famous_generals;
    }
   
};

    File.close();
    return 0;
}