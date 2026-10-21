#include <iostream>
#include <string>
#include <sstream>
#include <fstream>
using namespace std;
struct Node {
Battle battle;
Node* next;
};

struct Battle
{
string name, location;
string from_date, to_date;
int total_famous_generals;
string* list_famous_generals;
};
void addhead(Node*& L, Battle g){   
    Node*p = NULL;
    p->battle = g;
    p->next=L;
    L = p;
}
void deleteBattleArray(Battle* battles,int n){
    for(int i = 0; i < n; ++i){
       
    delete[] battles[i].list_famous_generals;
    
    }
}

Battle* prob1(string filename,int& n){
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
        Battle* a = new Battle[count];
        string info;
        int i = 0;
        while(getline(fin,line) && i < n){
            if(line.empty()) continue;
            stringstream ss(line);
            string segment;
            getline(ss,a[i].name,',');
            getline(ss,a[i].location,',');
            getline(ss,a[i].from_date,',');
            getline(ss,a[i].to_date,',');
            

            

        }   
}
        fin.close();
        
}

Node* prob2(Battle* battles, int n){
    Node* head = NULL;
    for ( int i = 0; i < n;i++){
        addhead(head,*battles);
    }
    return head;
}
int prob3(Node* head, string start_year, string end_year){

}

void prob4(Node*& head, string general){
    Node* p = head;
    int i = 0;
    while(p!=NULL){
        if(p->next->battle.list_famous_generals[i] == general){
            Node* del = p->next;
            p->next = del->next;
            delete del;
        }
        else{
            p=p->next;
        }
        i++;
    }
}
int main(){

}