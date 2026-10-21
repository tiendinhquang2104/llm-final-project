#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
#include <cstring>
#include <cmath>
using namespace std;

struct Battle {
    string name, location;
    string from_date, to_date;
    int total_famous_generals;
    string* list_famous_generals;
};

int demsodong(string filename){
    int dem=0;
    string line;
    ifstream fin;
    fin.open(filename);
    getline(fin,line,'\n');
    while (getline(fin,line,'\n')){
        dem++;
    }
    fin.close();
    return dem;
}

int demsopt(string list){
    int dem=1;
    for(char s: list){
        if(s==';'){
            dem++;
        }
    }
    return dem;
}

string* tach(string list){
    int n=demsopt(list);
    string* listfamous=new string[n];
    for(int i=0;i<n;i++){
        stringstream ss(list);
        string tmp;
        getline(ss,tmp,';');
        listfamous[i]=tmp;
    }
    return listfamous;
}

Battle* prob1(string filename, int& n){
    n=demsodong(filename);
    Battle* ketqua = new Battle[n];

    string line;
    ifstream fin;
    fin.open(filename);
    getline(fin,line,'\n');

    int i=0;
    while(getline(fin,line,'\n')){
        stringstream ss(line);
        string tam;

        getline(ss,ketqua[i].name,',');
        getline(ss,ketqua[i].location, ',');
        getline(ss,ketqua[i].from_date,',');
        getline(ss, ketqua[i].to_date,',');
        // getline(ss, tam , ',');
        // ketqua[i].total_famous_generals=stoi(tam);
        getline(ss, tam,'\n');
        ketqua[i].list_famous_generals=tach(tam);
        i++;
    }
    fin.close();
    return ketqua;
}

struct Node{
    Battle battle;
    Node* next;
};

struct List{
    Node* head;
    Node* tail;
};

Node* taonode(Battle p){
    Node* tmp = new Node();
    tmp->battle=p;
    tmp->next=NULL;
    return tmp;
}

void addtail(List &L, Battle p){
    Node* tmp=taonode(p);
    if(L.head==NULL){
        L.head=tmp;
        L.tail=tmp;
    }
    else{
        L.tail->next=tmp;
        L.tail=tmp;
    }
}

Node* prob2(Battle* battles, int n){
    List L;
    n=demsodong("battle.csv");
    battles=prob1("battle.csv",n);
    for(int i=0;i<n;i++){
        addtail(L,battles[i]);
    }
}

// int prob3(Node* head, string start_year, string end_year){
//     int dem=0;

//     return dem;
// }

int main(){
    int n=demsodong("battle.csv");
    cout<<n<<endl;
    Battle* a= new Battle [n];
    a= prob1("battle.csv", n);
    cout<<a[0].name<<" "<<a[19].name;
}