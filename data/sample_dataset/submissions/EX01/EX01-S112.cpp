#include<iostream>
#include<fstream>
#include<string>
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
General* prob1(string filename, int& n){
    ifstream fin;
    fin.open("filename");
    if(!fin.is_open()) cout<<"error";
    General* a = new  General[n] ;
    string buffer;
    int i=0;
    while(getline(fin,buffer,'\n')){
        General b;
        getline(fin,buffer,',');
        b.name=buffer;

        getline(fin,buffer,',');
        b.nationality=buffer;

        getline(fin,buffer,'-');
        b.born.day=stoi(buffer);

        getline(fin,buffer,'-');
        b.born.month=stoi(buffer);

        getline(fin,buffer,',');
        b.born.year=stoi(buffer);

        getline(fin,buffer,'-');
        b.death.day=stoi(buffer);
        getline(fin,buffer,'-');
        b.death.month=stoi(buffer);
        getline(fin,buffer,' ');
        b.death.year=stoi(buffer);
        getline(fin,buffer,',');
        b.death.era=buffer;
        string b1,b2, b3;
        getline(fin,buffer,',');
        b1=buffer;
        getline(fin,buffer,',');
        b2=buffer;
        getline(fin,buffer,',');
        b3=buffer;
        getline(fin,buffer,'\n');
        b.total_known_battles=stoi(buffer);

        a[i]=b;
        i++;
    }
    fin.close();
    return a;
}
Node* createnode(General a){
    Node* b;
    b->general=a;
    b->next=0;
    return b;
}
Node* prob2(General* generals, int n){
    Node* temp=0;
    Node* head=nullptr;
    int i=0;
    while(temp!=NULL&&i<=n){
        Node* New=createnode(generals[i++]);
        if(head==0){
            head=New;
            temp=head;
        }
        else{
            temp->next=New;
            temp=New;
        }
    }
    return head;
}
General prob3(Node* head){
    int ageM=head->general.death.year-head->general.born.year;
    Node *temp =head->next;
    int age=0;
    while(temp!=0){
        if(temp->general.death.era=="AD"&&temp->general.born.era=="AD"){
            age=temp->general.death.year-temp->general.born.year;
            if(age>ageM) ageM=age;
            temp=temp->next;
        } else if(temp->general.death.era=="AD"&&temp->general.born.era=="BC"){
            age=temp->general.death.year+temp->general.born.year;
            if(age>ageM) ageM=age;
            temp=temp->next;
        }
        else {
            age=temp->general.born.year+temp->general.death.year;
            if(age>ageM) ageM=age;
            temp=temp->next;
        }
    }
    temp=head;
    while(temp!=0){
        if(temp->general.death.era=="AD"&&temp->general.born.era=="AD"){
            age=temp->general.death.year-temp->general.born.year;
            if(age==ageM) return temp->general;
        } else if(temp->general.death.era=="AD"&&temp->general.born.era=="BC"){
            age=temp->general.death.year+temp->general.born.year;
            if(age==ageM) return temp->general;
        }
        else {
            age=temp->general.born.year+temp->general.death.year;
            if(age==ageM) return temp->general;
            temp=temp->next;
        }
    }
}
void prob4(Node*& head, string nationality){
    Node*temp=head;
    while(temp!=nullptr){
        temp->general.nationality=" ";
        temp=temp->next;
    }
}



int main(){
    string filename="general.csv";
    return 0;
}