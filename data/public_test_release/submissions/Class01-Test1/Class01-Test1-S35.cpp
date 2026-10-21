#include<iostream>
#include<string>
#include<fstream>
#include<cstring>
#include<math.h>
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

int cntLine(string filename){
    string line = "";
    int cnt = 0;
    ifstream fin(filename);
    getline(fin, line);
    while(getline(fin, line)) cnt++;

    fin.close();
    return cnt;
}
int cntData(string line){
    string word = "";
    int cnt = 1;
    for(char c : line){
        if(c == ',') cnt++;
    }
    return cnt;
}

Date dt(string line){
    string word = "";
    Date d;
    int ch = 0;
    for(char c : line){
        if(c != '-' && c != ' ') word += c;
        else if(ch == 0){
            d.day = stoi(word);
            word.clear();
            ch++;
        } else if(ch == 1){
            d.month = stoi(word);
            word.clear();
            ch++;
        } else if(ch == 2){
            d.year = stoi(word);
            word.clear();
            ch++;
        }
    }
    d.era = word;
    return d;
}

string *KBattle(string line){
    string word = "";
    int m = 1;
    for(char c : line){
        if( c == '|') m++;
    }
    string *ans = new string[m];
    int i =0;
    for(char c : line){
        if(c != '|') word += c;
        else{
            ans[i++] = word;
            word.clear();
        }
    }
    ans[i] = word;
    return ans;
}

General splitOnLine(string line){
    General s;
    int k = 0;
    string word = "";
    string *ans = new string[cntData(line)];
    for(char c : line){
        if(c != ',') word += c;
        else{
            ans[k++] = word;
            word.clear();
        }
    }

    ans[k] = word;

    int h = 0;
    s.name = ans[0];
    s.nationality = ans[1];

    s.born = dt(ans[2]);
    s.death = dt(ans[3]);

    s.total_known_battles = stoi(ans[9]);
    s.known_battles = KBattle(ans[4]);

    delete []ans;

    return s;
}

General* prob1(string filename, int& n){
    n = cntLine(filename);
    General *g = new General[n];
    string line = "";
    ifstream fin(filename);

    for(int i = 0; i < n; i++){
        g[i] = splitOnLine(line);
    }

    fin.close();
    return g;
}

void pushBack(Node* &head, General x){ 
    Node* newNode = new Node;

    if(head == nullptr){
        head = newNode;
        return;
    }
    Node *p = head;
    for(p; p->next; p = p->next);
    p->next = newNode;
}

Node* prob2(General* generals, int n){
    Node *head = nullptr;
    for(int i = 0; i < n; i++){
        pushBack(head, generals[i]);
    }
    return head;
}

General prob3(Node* head){
    General p3;
    if(!head && !head->next) return;

    Node* p =head->next;
    Node* pre = head;
    Node* ans = head;
    for(p; p; p = p->next){
        if( abs( (p->general.death.year) - p->general.born.year ) > abs ( pre->general.death.year - pre->general.born.year ) ) { 
            ans = p;
        }
        pre = p;
    }

    p3 = ans->general;
    return p3;
}

void removeHead(Node *&head){
    if(head == nullptr) return;
    Node *p = head;
    head = head->next;
    delete p;
}

void prob4(Node*& head, string nationality){
    Node * p = head;
    Node *pre = nullptr;
    while(p){
        if( p->general.nationality == nationality ) {
            if(pre == nullptr){
                removeHead(head);
            }
            else {
                pre->next = p->next;
                delete p;
                p = pre->next;
            }
        }

        p = p->next;
        pre = p;
    }
}
