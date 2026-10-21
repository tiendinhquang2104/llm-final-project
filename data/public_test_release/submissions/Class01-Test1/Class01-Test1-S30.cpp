#include <iostream>
#include <string>
#include <fstream>
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
Node* createnode(General g){
    Node*p = NULL;
    p->general = g;
    p->next = NULL;
    return p;
}
void addhead(Node*& L, General g){
    Node*p = NULL;
    p->general = g;
    p->next=L;
    L = p;
}
int getYear(string s){
    int lastDash = s.rfind('-');
    if(lastDash == string::npos) return 0;
    int pos = lastDash+1;
    int year = 0;
    while(pos<s.size() && isdigit(s[pos])){
        year = year *10 + (s[pos]-'0');
    }
    return year;
}
int getmonth(string s){
    int i = 0;
    int month = 0;
    while(i<s.size() && isdigit(s[i])){
        month = month *10 + (s[i] - '0');
    }
    return month;
}
int getDay(string s){
    int i = 0;
    while(i<s.size() && s[i]!='-'){
        i++;
}
string getera(string s){
    int i = s.rfind(' ');
    string era = "";
    while(i<s.size()){
        era += s[i];
    }
    return era;
}
    i++;
    int day = 0;
    while(i<s.size() && isdigit(s[i])){
        day = day*10 + (s[i] -'0');
    }
    return day;
}
General* prob1(string filename, int& n){
    ifstream fin(filename);
    if(fin.is_open()){
        string header;
        getline(fin,header);
        int count = 0;
        string line;
        while(getline(fin,line)){
            count++;
        }
        fin.clear();
        fin.seekg(0,ios::beg);
        getline(fin,header);
        General* a = new General[count];
        string info;
        int i = 0;
        while(i<count && getline(fin,a[i].name,',')){
            int tempday,tempmonth,tempyear, tempera;
            getline(fin,a[i].nationality,',');
            tempmonth = getmonth(info);
            a[i].born.month = tempmonth;
            tempday = getDay(info);
            a[i].born.day = tempday;
            tempyear = getYear(info);
            a[i].born.year = tempyear;
            getline(fin,a[i].born.era,',');
            a[i].total_known_battles = stoi(info);
            getline(fin,info);
        }
        fin.close();
        return a;
    }
}
Node* prob2(General* generals, int n){
    Node* head = NULL;
    for ( int i = 0; i<n;i++){
        addhead(head,*generals);
    }
    return head;
}
void prob4(Node*& head, string nationality){
    Node* p = head;
    while(p!=NULL){
        if(p->next->general.nationality == nationality){
            Node* del = p->next;
            p->next = del->next;
            delete del;
        }
        else{
            p=p->next;
        }
    }
}
int main(){

}