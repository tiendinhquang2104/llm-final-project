#include <iostream>
#include <fstream>
#include <string>
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
};
int countLine (string filename, int& n){
    ifstream file (filename);
    int cnt = 0;
    string line;
    getline (file, line);
    while (getline(file, line)){
        cnt++;
    }
    file.close();
    return cnt;
}
//Prob1:
General* prob1(string filename, int& n){
    ifstream file(filename);
    if(!file.is_open()){
        return 0;
    }
    int b = countLine (filename, n);
    General* a = new General[n];
    string line;
    getline(file, line);
    while (getline(file, line)){
        for(int i = 0; i < b; i++){
            getline (file, a[i].name, ',');
            getline (file, a[i].nationality, ',');
            string line1;
            getline (file, line1);
            a[i].born.day = stoi(line1);
            a[i].born.month = stoi(line1);
            a[i].born.year = stoi(line1);
            getline(file, a[i].born.era, ',');
            string line2;
            getline (file, line2);
            a[i].death.day = stoi(line2);
            a[i].death.month = stoi(line2);
            a[i].death.year = stoi(line2);
            getline(file, a[i].death.era, ',');
            int dem = 0;
            string line3;
            getline(file, line3);
            if(line3 == "|"){
                dem++;
            }
            for (int j = 0; j <= dem; j++){
                getline (file, *a[i].known_battles, '|');
            }
            string line4;
            getline(file, line4);
            a[i].total_known_battles = stoi(line4);
        }
    file.close();
}
}

//Prob2:
struct node{
    General data;
    node* next;
};
node* makeNode (General* generals){
    node* newNode = new node();
    newNode->data = *generals;
    newNode->next = NULL;
    return newNode;
}
Node* prob2(General* generals, int n){
    node* newNode = makeNode(generals);
    node *head = newNode;
    node* temp = head;
    while (head == NULL){
        head = newNode;
        return;
    }
    while (temp->next != NULL){
        temp = temp->next;
    }
    temp->next = newNode;
}

