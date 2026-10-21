#include <iostream>
#include <fstream>
#include <cstdlib>
#include <string>
#include <sstream>
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

int numbers(string filename){
    ifstream fin(filename);
    if (!fin.is_open())
    cout << "mở file thất bại";
    int count =0;
    string line;
    getline(fin,line);
    while(getline(fin,line)){
        count++;
    }
    fin.close();
    return count;
}

int dividename(string line){
    int count =0;
    stringstream ss(line);
    string token;
    while(getline(ss,token,';')){
    count++;
    }
     return count;
}

string *listfamous(string line){
    int n= dividename(line);
    string* famous = new string[n];
    stringstream ss(line);
    string token;
    int i=0;
    while (getline(ss,token,';')){
        famous[i] = token;
    }
    return famous;
}   

Battle* prob1(string filename, int& n){
    ifstream fin(filename);
    if (!fin.is_open())
    cout << "mở file thất bại";
    Battle* Bat= new Battle[n];
    string line;
    getline(fin,line);
    int i=0;
    while(getline(fin,line)){
        string token;
        stringstream ss(line);
        getline(ss,token,',');
        Bat[i].name = token;

        getline(ss,token,',');
        Bat[i].location = token;

        getline(ss,token,',');
        Bat[i].from_date = token;

        getline(ss,token,',');
        Bat[i].to_date = token;

        getline(ss,token,',');
        getline(ss,token,',');
        getline(ss,token,'\n');
        Bat[i].total_famous_generals= dividename(token);
        Bat[i].list_famous_generals = listfamous(token);
        i++;
    }

    fin.close();
    return Bat;
}


Node* createnode(Battle battle ){
    Node* newnode  = new Node;
    newnode->battle = battle;
    newnode->next = NULL;
    return newnode;
}

Node* prob2(Battle* battles, int n){
    Node* head = NULL;
    

    for (int i=0; i<n; i++){
        Node* newnode = createnode(battles[i]);
        if (head == NULL){
            head = newnode;
        }
        else {
            Node* cur= head;
            while (cur->next != NULL){
                if (cur->next == NULL){
                    cur->next = newnode;
                    break;
                }
                cur = cur->next;

            }
        }

    }

}



int main(){
    int n=numbers("50-european-battles-first-20.txt");
    Battle* Bats =prob1("50-european-battles-first-20.txt",n);
    cout << Bats[0].name <<" "<< Bats[0].location<<" "<< Bats[0].from_date<<" "<< Bats[0].to_date<<" "<< Bats[0].total_famous_generals <<" "<<Bats[0].list_famous_generals;
    return 0;
    
}