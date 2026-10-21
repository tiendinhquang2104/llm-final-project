#include<iostream>
#include<fstream>
#include<cstring>
#include<string>
#include<sstream>
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
Date parsedate(string date) {
    Date d;
    d.day = stoi(date.substr(0,2));
    d.month = stoi(date.substr(3,2));
    d.year = stoi(date.substr(6, date.find(' ') - 6));
    d.era = date.substr(date.find(' ') + 1, 2);
    return d;
}
General* prob1(string filename, int& n) {
    ifstream fin(filename);
    if(fin.is_open()) {
        string header;
        getline(fin, header);
        string line;
        n = 0;
        while(getline(fin,line)) {
           n++; 
        }
        fin.clear();
        fin.seekg(0, ios::beg);
        getline(fin,header);
        string temp;
        General * a = new General[n];
        int i = 0;
        while(i < n && getline(fin, temp, ',')) {
            a[i].name = temp;
            getline(fin, temp, ',');
            a[i].nationality = temp;
            getline(fin, temp, ',');
            a[i].born = parsedate(temp);
            getline(fin, temp, ',');
            a[i].death = parsedate(temp);
            getline(fin, temp, ',');
            a[i].known_battles = &temp;
            getline(fin, temp, ',');
            getline(fin, temp,',');
            getline(fin, temp, ',');
            getline(fin, temp);
            a[i].total_known_battles = stoi(temp);
            i++;
        }
        return a;
    }else {
        n = 0;
        return nullptr;
    }
}
Node* prob2(General* generals, int n) {
    Node * a = new Node;
    for(int i = 0; i < n; i++) {
        a[i].general.name = generals[i].name;
        a[i].general.nationality = generals[i].nationality;
         a[i].general.born = generals[i].born;
         a[i].general.death = generals[i].death;
         a[i].general.known_battles = generals[i].known_battles;
         a[i].general.total_known_battles = generals[i].total_known_battles;
    }
    a[n].next = nullptr;
    return a;
}
int caculateage(Date born, Date death) {
   if(born.era == "BC") born.year = -born.year;
   if(death.era == "BC") death.year = -death.year;
    int age = death.year - born.year;
    if(death.month < born.month) age--;
    else if(death.month == born.month && death.day < born.day) age--;
    return age;
}
General prob3(Node* head) {
    
    Node * cur = head;
    General find;
    int maxage = caculateage(head->general.born, head->general.death);
    cur = cur->next;
    while(cur){
        if(caculateage(cur->general.born, cur->general.death) > maxage) {
            find = cur->general;
            maxage = caculateage(cur->general.born, cur->general.death);
        }
    }
    return find;
}
void prob4(Node*& head, string nationality) {
    if(head == nullptr) return;
    Node * cur = head;
    Node * prev = nullptr;
    while(cur) {
        if(cur->general.nationality == nationality) {
            Node * temp = cur;
            prev->next = cur->next;
            cur = cur->next;
            delete temp;
        }
        else {
            prev = cur;
            cur = cur->next;
        }
    }
}
















int main() {
   
    return 0;
}