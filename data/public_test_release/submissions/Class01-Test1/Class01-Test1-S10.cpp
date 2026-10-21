#include<fstream>
#include<iostream>
#include<cstring>
#include<cstdlib>
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
int countFile(string filename)
{
    int re=0;
    ifstream f;
    f.open(filename);
    if(!f.is_open())
    return 0;
    string a;
    getline(f,a,'/n');
    while(getline(f,a,'/n'))
    {
        re++;
    }
    f.close();
    return re;
}
Date strTodate(string s)
{
    Date temp;
    char arr[50];
    char* token;
    strcpy(arr,s.c_str());
    token=strtok(arr,"- ");
    temp.day=atoi(token);
    token=strtok(arr,"- ");
    temp.month=atoi(token);
    token=strtok(arr,"- ");
    temp.year=atoi(token);
    token=strtok(arr,"/n");
    temp.era=token;
    return temp;
}
General* prob1(string filename, int& n)
{
    int line=countFile(filename);
    n=line;
    ifstream f;
    f.open(filename);
    if(!f.is_open())
    return 0;
    string a;
    getline(f,a,'/n');
    char b[20];
    General * arr= new General[line];
    for(int i=0; i<line; i++)
    {
        getline(f,arr[i].name,',');
        getline(f,arr[i].nationality,',');
        getline(f,a,',');
        arr[i].born=strTodate(a);
        getline(f,a,',');
        arr[i].death=strTodate(a);
        getline(f,arr[i].known_battles,',');
        getline(f,a,',');
        getline(f,a,',');
        getline(f,a,',');
        getline(f,a,',');
        arr[i].total_known_battles=stoi(a);
    }
    return arr;
}
struct Node {
General general;
Node* next;
};
Node* prob2(General* generals, int n)
{
    Node* head= new Node;
    Node* phead=head;
    Node* pcurr=head;
    head->general=generals[0];
    head->next=nullptr;
    for(int i=1;i<n;i++)
    {
        Node* curr= new Node;
        pcurr->next=curr;
        curr->general=generals[i];
        curr->next=nullptr;
    }
    return phead;
}
void prob4(Node*& head, string nationality)
{
    Node* pcurr=head;
    Node* ppre=head;
    if(head->general.nationality==nationality)
    {
        head=head->next;
        delete pcurr;
        pcurr=head;
        ppre=pcurr;
    }
    while(pcurr)
    {
        if(pcurr->next->next==nullptr)
        {
            if(pcurr->next->general.nationality==nationality)
    {
        pcurr=pcurr->next;
        delete pcurr;
        ppre->next=nullptr;
    } 
        }
       if(pcurr->general.nationality==nationality)
    {
        pcurr=pcurr->next;
        delete ppre;
        ppre=pcurr;
    } 
    else
    pcurr=pcurr->next;
    ppre=pcurr;
    }
}
int main()
{
    cout<<"hello ";
    return 0;
    
}