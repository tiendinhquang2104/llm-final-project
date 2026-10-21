#include<iostream>
#include<fstream>
#include<sstream>
#include<string>
using namespace std;
struct Battle {
string name, location;
string from_date, to_date;
string CountriesInvolved;
float Casualties;
string ListFamousGenerals;
int total_famous_generals;
string* list_famous_generals;
};
struct Node {
Battle battle;
Node* next;
};
struct List{
    Node pHead;
    Node pTail;
};
int counting(string filename){
    int count=0;
    ifstream infile(filename);
       if(!infile){
        return -1;
    }
    string line;
    getline(infile,line);
    while(getline(infile,line)){
        count++;
    }
    infile.close();
    return count;
}
void addTail(Battle battles){
    Node*newNode=new Node;
    newNode->battle=battles;
    newNode->next=nullptr;
}
Node* prob2(Battle* battles, int n){
    for(int i=0;i<n;i++){
        Node *ex=addTail(battles[i]);
    }
}
Battle* prob1(string filename, int& n){
    int count;
    count=counting(filename);
    Battle *ex=new Battle[count];
    int i=0;
    ifstream infile(filename);
    string line;
    getline(infile,line,'\0');
    while(getline(infile,line)){
        stringstream ss(line);
        string token;
        getline(ss,ex[i].name,',');
        getline(ss,ex[i].location,',');
        getline(ss,ex[i].from_date,',');
        getline(ss,ex[i].to_date,',');
        getline(ss,ex[i].CountriesInvolved,',');
        getline(ss,token,',');
        ex[i].Casualties=stof(token);
        getline(ss,ex[i].ListFamousGenerals,'\0');
        i++;
    }
    infile.close();
    return ex;

}
int main(){
    int n=counting("battles.csv");
    cout<<n;
    return;
}