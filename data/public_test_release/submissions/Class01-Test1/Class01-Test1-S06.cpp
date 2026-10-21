#include <iostream>
#include <cstdlib>
#include <sstream>
#include <string>
#include <cstring>
#include <fstream>
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
Date splitdate(string s)
{
    Date d = {0, 0, 0};
    stringstream ss(s);
    string token;
    if (s.empty())
    {
        return d;
    }
    getline (ss, token, '-');
    d.day = atoi(token.c_str());
    getline (ss, token, '-');
    d.month = atoi(token.c_str());
    getline (ss, token, '-');
    d.year = atoi(token.c_str());
    return d;
}
void splitdata(string s, string *&arr, int &size)
{
    stringstream ss(s);
    string token;
    if (s.empty())
    {
        size = 0;
        arr = NULL;
        return;
    }
    int i = 0;
    size = 1;
    for (char c : s)
    {
        if (c == '|')
        size++;
    }
    arr = new string [size];
    while(getline(ss, token, '|'))
    {
        arr[i++] = token;
    }
}
void splitline (string line, General &g)
{
    string token;
    stringstream ss(line);
    if (getline(ss, token, ','))
    g.name = token;
    if(getline(ss, token, ','))
    g.nationality = token;
    if (getline(ss, token, ','))
    g.born = splitdate(token);
    if (getline(ss, token, ','))
    g.death = splitdate(token);
    if (getline(ss, token, ','))
    splitdata(token, g.known_battles, g.total_known_battles);
}
Node *createnode (General g)
{
    Node *nn = new Node;
    nn->general = g;
    nn->next = NULL;
    return nn;
}
void addtail (Node *&head, General &g)
{
    Node *nn = createnode(g);
    if ( head == NULL )
    {
        head  = nn;
        return;
    }
    Node *temp = head;
    while (temp -> next != NULL)
    {
        temp = temp->next;
    }
    temp->next = nn;
}
void readfile (string filename, Node *&head)
{
    ifstream file (filename);
    if(!file.is_open())
    {
        cout << "khong mo duoc";
        return;
    }
    string line;
    getline(file, line);
    while (getline(file, line))
    {
        General g;
        splitline(line, g);
        addtail(head, g);

    }
    file.close();
}
void printlist (Node *&head, General &g)
{
    Node *temp = head;
    while (temp != NULL)
    {
        cout << g.name << endl;
        cout << g.nationality << endl;
        cout << g.born.day << '-' << g.born.month << '-' << g.born.year << endl;
        cout << g.death.day << '-' << g.death.month << '-' << g.death.year << endl;
        for (int i = 0; i < g.total_known_battles; i++)
        {
            cout << g.known_battles[i] << endl;
        }
        temp = temp->next;
    }
}
General* prob1(string filename, int& n)
{
    ifstream file (filename);
    if (!file.is_open())
    { 
    }
    string line;
    getline (file, line);
}
Node* prob2(General* generals, int n)
{

}
General prob3(Node* head)
{

}
void prob4(Node*& head, string nationality)
{
    Node *temp = head;
    if (head == NULL)
    {
        return;
    }
    while (temp->next != NULL)
    {
        if (temp->general.nationality == nationality)
        {
            Node *dele = temp->general;
            temp = temp->next;
            delete dele;
        }
        temp = temp->next;
    }
}
