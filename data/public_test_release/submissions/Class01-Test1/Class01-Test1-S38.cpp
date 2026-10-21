#include <iostream>
#include <fstream>
#include <string>
#include <cstring>
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
struct Node{
    General data;
    Node* next;
};
Node* CreateNewNode(Node* &head, General g){
    Node* p = nullptr;
    p->data = g;
    p->next = nullptr;
    return p;
}
Node* append(Node* &head, General g){
    Node* p = CreateNewNode(head, g);
    if(head == nullptr){
        head = p;
    }
    Node* cur = head;
    while(cur->next != nullptr){
        cur = cur -> next;
    }
    cur -> next = p;
    return p;
}
Date ChiaNgayGio(const char *DateDoi){
    Date d;
    string s(DateDoi);
    d.day = stoi(s.substr(0,2));
    d.month = stoi(s.substr(3,2));
    d.year = stoi(s.substr(6, s.find("") - 6));
    if(s.find("BC")) d.era = "BC";
    else d.era = "AD";
    return d;
}
General* prob1(string filename, int& n){
    ifstream fin(filename);
    if(!fin.is_open()){
        return nullptr;
    }
    string line;
    getline(fin, line);
    int count = 0;
    while(getline(fin, line)){
        count++;
    }
    n = 0;
    fin.clear();
    fin.seekg(' ', ios::beg);
    getline(fin, line);
    General g;
    Date d;
    General *arr = new General[count];
    while(n < count && getline(fin, g.name, ',')){
        getline(fin, g.nationality,',');
        getline(fin, line);
        getline(fin, line);
        getline(fin, line, ',');
        getline(fin, line, ',');
        getline(fin, line, ',');
        getline(fin, line, ',');
        getline(fin, line);
        arr[n].name = g.name;
        arr[n].nationality = g.nationality;
        n++;
    }
    return arr;
}
Node* prob2(General* generals, int n){
    Node* head = nullptr;
    for(int i = 0; i < n; i++){
        append(head, generals[i]);
    }
    return head;
}
void prob4(Node*& head, string nationality){
    if(head == nullptr) return;
    if(head != nullptr && head->data.nationality == nationality){
        Node* temp = head;
        head = head -> next;
        delete temp;
    }
    Node* cur = head;
    while(cur != nullptr){
        if(cur ->next -> data.nationality == nationality){
            Node* temp = cur->next;
            cur -> next = temp -> next;
            delete temp;
        }
        else cur = cur -> next;
    }
}
int main(){
    return 0;
}