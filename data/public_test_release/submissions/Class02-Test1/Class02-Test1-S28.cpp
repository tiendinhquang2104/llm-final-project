#include <iostream>
#include <string>
#include <sstream>
#include <fstream>

using namespace std;

struct Battle{
    string name, location;
    string from_date, to_date;
    int total_famous_generals;
    string* list_famous_generals;
}

struct Node{
    Battle battle;
    Node* next;    
}

Battle spilit_line(string line){
    stringstream ss(line);
    int Col = 0;
    while(getline(ss, s, ',')){
        Col++;
        switch(Col){
            case 1:
            tmp.name = s;
            break;
            case 2:
            tmp.location = s;
            break;
            case 3:
            tmp.from_date = s;
            break;
            case 4:
            tmp.to_date = s;
            break;
            case 5:
            break;
            case 6:
            tmp.total_famous_generals = stoi(s);
            break;
            case 7:
            tmp.list_famous_generals = s;
            break;

            default:
            break
        }
    }
    return tmp;
}

Battle* prob1(string filename, int &n){
    fstream fs;
    fs.open(filename);
    string line;
    getlien(fs, line, '\n');

    Battle* arr = new Battle[25];
    while(getline(fs, line, '\n')){
        n++;
        arr[n] = spilit_line(line);
    }

    return arr;
}

Node* creatnode(Battle battle){
    Node* newnode = new Node();
    newnode.battle = battle;
    newnode.next = NULL;
    return newnode;
}

Node* prob2(Battle* battle, int n){
    Node* head = NULL;
    Node* next = NULL;
    for(int i = 0; i < n; i++){
        Battle newnode = creatnode(battle[i]);
        if(i == 0){
            head = newnode;
            next = head;
        }else{
            next.next = newnode;
            next = newnode;
        }
    }
    return head;
}

int prob3(Node* head, string start_year, string end_year){
    Node* cur = head;
    int count = 0;
    while(cur != NULL){
        if(cur.battle.from_date == start_year && cur.battle.to_date == end_year){
            count ++;
        }
        cur = cur.next;
    }

    return count;
}

string* spilit_general(string list_famous_generals, int &n){
    string* tmp = new string[1000];
    int count = 0;
    while(getline(list_famous_generals, tmp, ';')){ 
        tmp[n];
        n++;
    }
    return tmp;
}

void prob4(Node* &head, string general){
    Node* cur = head;
    Node* next = NULL;

    int n = 0;
    string* s = new string[1000];
    while(cur != NULL){
        s = spilit_general(cur.battle.list_famous_generals, n);
        for(int i = 0; i <= n; i++){
            if(s[i] == general){
                
            }
        }
    }
}

int main(){
    string namefile = "50-european-battles-first-20.csv";
    int n = 0;
} 