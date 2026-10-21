#include <iostream>
#include <string>
#include <fstream>
using namespace std;
//generals.csv

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

int countLine(string filename){
    int n = 0;
    ifstream fin;
    fin.open(filename);
    if (!fin.is_open())
    {
        return 0;
    }
    string line;
    getline(fin,line);
    while (getline(fin,line))
    {
        ++n;
    }
    fin.close();
    return n;
}

//
int countDelimeter(string s){
    int n = 1;
    for (int i = 0; i < s.size(); i++) 
    {
        if (s[i] == '|')
        {
            ++n;
        }
    }
    return n;
}
//09-08-1157 AD
Date toDate(string s)
{
    Date person;
    int pos_space = s.find(' ');
    person.era = s.substr(pos_space+1);
    int first = s.find('-');
    int last = s.find('-',first+1);
    person.day = stoi(s.substr(0,first));
    person.month = stoi(s.substr(first+1,last - first - 1));
    person.year = stoi(s.substr(last+1,pos_space - last - 1));
    return person;
}

string* split(string s,int &n)
{
    n = countDelimeter(s);
    string* person = new string[n];
    string line = "";
    int index = 0;
    for (int i = 0; i <= s.size(); i++)
    {
        if (i == s.size() || s[i] == '|')
        {
            person[index++] = line;
            line = "";
        }
        else
        {
            line += s[i];
        }
    }
    return person;
}
General* prob1(string filename, int& n)
{
    n = countLine(filename);
    if (n <= 0 )
    {
        return NULL;
    }
    General* person = new General[n];
    
    ifstream fin;
    fin.open(filename);
    if (!fin.is_open())
    {
        return NULL;
    }
    string line = "";
    getline(fin,line);
//     string name, nationality;
// Date born, death;
// int total_known_battles;
// string* known_battles;

//Name,Nationality,Born,Death,KnownBattles,ListOfMedals,KnownPosition,LastPosition,TotalWonBattles
    for (int i = 0; i < n; i++)
    {
        getline(fin,line,',');
        person[i].name = line;

        getline(fin,line,',');
        person[i].nationality = line;

        getline(fin,line,',');
        person[i].born = toDate(line);

        getline(fin,line,',');
        person[i].death = toDate(line);

        getline(fin,line,',');
        person[i].known_battles = split(line,person[i].total_known_battles);

        getline(fin,line,',');

        getline(fin,line,',');

        getline(fin,line,',');

        getline(fin,line);
    }
    fin.close();
    return person;
}
struct Node {
General general;
Node* next;
};

Node* createNode(General data)
{
    Node* p = new Node;
    p->general = data;
    p->next = NULL;
    return p;
}

void addTail(Node* &head,General data)
{
    Node* p = createNode(data);
    if (head == NULL)
    {
        head = p;
        return;
    }
    Node* cur = head;
    while (cur ->next != NULL)
    {
        cur = cur ->next;
    }
    cur->next = p;
}

Node* prob2(General* generals, int n)
{
    Node* head = NULL;
    for (int i = 0; i < n; i++)
    {
        addTail(head,generals[i]);
    }
    return head;
}

int age(General person)
{
    int agee = 0;
    if (person.born.era == "AD")
    {
        agee = person.death.year - person.born.year;
    }
    else if (person.born.era == "BC")
    {
        agee = person.born.year - person.death.year;
    }
    return agee;
}

General prob3(Node* head)
{
    General person;
    if (head == NULL)
    {
        return person;
    }
    Node* cur = head;
    int max = 0;
    while (cur != NULL)
    {
        int agee = age(cur->general);
        if (agee > max);
        {
            max = agee;
            person = cur->general;
        }
        cur = cur ->next;
    }
    return person;
}

void prob4(Node*& head, string nationality)
{
    if (head == NULL)
    {
        return;
    }
    while (head != NULL && head->general.nationality == nationality)
    {
        Node* del = head;
        head = head ->next;
        delete [] del->general.known_battles;
        delete del;
    }

    if (head == NULL)
    {
        return;
    }

    Node* prev = head;
    Node* cur = head ->next;
    
    while (cur != NULL)
    {
        if (cur->general.nationality == nationality)
        {
            prev->next = cur->next;
            delete [] cur->general.known_battles;
            delete cur;
            cur = prev->next;
        }
        else
        {
            prev = cur;
            cur = cur->next;
        }
    }
}

int main()
{
    int n;
    General* person = prob1("generals.csv",n);
    Node* head = prob2(person,n);
    return 0; 
}