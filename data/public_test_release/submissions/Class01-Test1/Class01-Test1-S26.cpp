#include <iostream>
#include <fstream>
#include <cstring>
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
int CountLine(string filename)
{
    int n = 0;
    string ignore_line = "";
    string line;
    fstream file;
    file.open(filename);
    getline(file,ignore_line, '\n');
    while(getline(file, line, '\n'))
    {
        n++;
    }
    file.close();
    return n;
}
General* prob1(string filename, int& n)
{
    n = CountLine(filename);
    General* pG = new General[n];
    string ignore_line = "";
    string line = "";
    fstream file;
    file.open(filename);
    getline(file, ignore_line, '\n');
    for(int i = 0; i <n; i++)
    {
        getline(file, line, ',');
        pG[i].name = line;
        getline(file, line, ',');
        pG[i].nationality = line;

        getline(file, line, '-');
        pG[i].born.day = stoi(line);
        getline(file, line, '-');
        pG[i].born.month = stoi(line);
        getline(file, line, ' ');
        pG[i].born.year = stoi(line);
        getline(file, line, ',');
        pG[i].born.era = line;

        getline(file, line, '-');
        pG[i].death.day = stoi(line);
        getline(file, line, '-');
        pG[i].death.month = stoi(line);
        getline(file, line, ' ');
        pG[i].death.year = stoi(line);
        getline(file, line, ',');
        pG[i].death.era = line;

        getline(file, line, ',');
        pG[i].total_known_battles = stoi(line);
        getline(file,line, ',');
        if(pG[i].known_battles != NULL)
        pG[i].known_battles = new string(line);
        else
        pG[i].known_battles = NULL;
        getline(file, line, ',');
        getline(file, line, ',');
        getline(file, line, ',');
        getline(file, line, ',');
        pG[i].total_known_battles = stoi(line);
    }
    file.close();
    return pG;
}


Node* CreateNode(General* p)
{
    Node* pNew = new Node;
    pNew->general.name = p->name;
    pNew->general.nationality = p->nationality;

    pNew->general.born.day = p->born.day;
    pNew->general.born.month = p->born.month;
    pNew->general.born.year = p->born.year;
    pNew->general.born.era = p->born.era;

    pNew->general.death.day = p->death.day;
    pNew->general.death.month = p->death.month;
    pNew->general.death.year = p->death.year;
    pNew->general.death.era = p->death.era;

    pNew->general.total_known_battles = p->total_known_battles;
    pNew->general.known_battles = new string(*(p->known_battles));
    return pNew;
}
void AddTail(Node*& pHead, General* p)
{
    Node* pNew = CreateNode(p);
    Node*pCurr = pHead;
    if(pHead == NULL)
        pHead = pNew;
    else
    {
        while(pCurr -> next != NULL)
        pCurr = pCurr -> next;
    }
    pCurr -> next = pNew;
}
Node* prob2(General* generals, int n)
{
    Node* pHead = NULL;
    for(int i = 0; i<n ; i++)
        AddTail(pHead, &generals[i]);
    return pHead;
}
void DisplayList(Node* pHead)
{
    Node* pCurr = pHead;
    while(pCurr -> next != NULL)
    {
        cout<<pCurr->general.known_battles<<endl;
        cout<<pCurr->general.name<<endl;
        pCurr = pCurr -> next;
    }

}
int main()
{

    string filename= "50-best-european-generals-cleaned-first-20.csv";
    int n = CountLine(filename);
    cout<<n;
    General* p = prob1(filename,n);
    Node* pHead = NULL;
    prob2(p, n);
    DisplayList(pHead);
    return 0;
}

