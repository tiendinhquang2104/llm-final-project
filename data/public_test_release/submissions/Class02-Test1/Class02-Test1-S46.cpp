#include <iostream>
#include <fstream>
#include <string>
#include <cstring>
#include <sstream>
#include <cmath>
using namespace std;
struct Battle{
    string name, location;
    string from_date, to_date;
    int total_famous_generals;
    string *list_famous_generals;
};
struct node{
    Battle battle;
    node *next;
};
int fileSize(string filename){
    ifstream fin(filename);
    string line;
    getline(fin,line,'\n');
    int count = 0;
    while(getline(fin,line,'\n')){
        count++;
    }
    fin.close();
    return count;
}
Battle *prob1(string filename, int &n){ //BattleName,Location,FromDate,ToDate,CountriesInvolved,Casualties,ListFamousGenerals
    ifstream fin(filename);/*Write a function to read all records from the file filename into a dynamically allocated array of Battle. The
order of battles in the array must match their order in the file.*/
    string line;
    n = fileSize(filename);
    Battle *kq = new Battle[n];
    getline(fin,line);
    int i = 0;
    while(getline(fin,line)){
        stringstream ss(line);
        getline(ss,kq[i].name,',');
        getline(ss,kq[i].location, ',');
        getline(ss,kq[i].from_date, ',');
        getline(ss,kq[i].to_date,',');
        string tfg, lfg;
        getline(ss,tfg,',');
        kq[i].total_famous_generals = stoi(tfg);
        getline(ss,lfg,'\n');
        kq[i].list_famous_generals = &lfg;
        i++;
    }
    fin.close();
    return kq;
}
node *createNode(Battle x){
    node *p = new node;
    p->battle = x;
    p->next = nullptr;
    return p;
}
void appendNode(node *&head, Battle x){
    node *p = createNode(x);
    if(head==nullptr){
        head = p;
        return;
    }else{
        head->next = p;
        head = p;
        return;
    }
}
node *prob2(Battle battles, int n){/*head=1st battle, ->next = */
    Battle *b = prob1("50-european-battles-first-20.csv",n);
    node *head = nullptr;
    for(int i=0; i<n; i++){
        appendNode(head,b[i]);
    }
    return head;
/*Create a linked list from a given array of Battle. The order of battles in the list must match their order in
the array.*/
}
struct dmy{
    string d,m,y;
};
string spiltFromYear(string filename, string line){
    int n;
    Battle *a = prob1(filename,n);
    stringstream ss(line);
    dmy ex;
    ex.d = a->from_date.substr(0,2);
    ex.m = a->from_date.substr(3,2);
    ex.y = a->from_date.substr(6,4);
    return ex.y;
}
string spiltToYear(string filename, string line){
    int n;
    Battle *a = prob1(filename,n);
    stringstream ss(line);
    dmy ex;
    ex.d = a->to_date.substr(0,2);
    ex.m = a->to_date.substr(3,2);
    ex.y = a->to_date.substr(6,4);
    return ex.y;
}
int prob3(node* head, string start_year, string end_year){
    string filename, line;
    int count = 0;
    start_year = spiltFromYear(filename,line);
    end_year = spiltToYear(filename,line);
    return count;
    /*Count the total number of battles that occurred within the year range [start_year, end_year] (inclusive)
using the list created in Problem 2. You must operate in-place (i.e., without using extra lists, arrays, etc.).*/
}
void prob4(node*& head, string general){
    /*Remove all battles in which a specific general did not participate from the list created in Problem 2. You
must remove nodes in-place (i.e., without using extra lists, arrays, etc.).*/
}
void printList(node *head){
    node *cur = head;
    while(cur != nullptr){
        cout << cur->battle.name;
        cur = cur->next;
    }
}
int main(){
    
    
    return 0;
}