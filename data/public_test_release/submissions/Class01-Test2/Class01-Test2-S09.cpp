#include<iostream>
#include<sstream>
#include<cstring>
#include<fstream>
#include<vector>
using namespace std;
struct Date {
int day, month, year;
string era; // AD or BC
};
struct Node {
General general;
Node* left;
Node* right;
};
struct General {
string name, nationality;
Date born, death;
vector<string> known_battles;
};
Date SplitDate(string a)
{
    stringstream ss(a);
    Date d;
    char dash;
    ss>>d.day>>dash>>d.month>>dash>>d.year>>d.era;
    return d;
}
vector<string> SplitBattle(string a)
{
    vector<string> arr;
    stringstream ss(a);
    string tokens;
    while(getline(ss,tokens,'|'))
    {
        arr.push_back(tokens);
    }
    return arr;
}
vector<General> prob1(string filename)
{
    vector<General> arr;
    ifstream fin(filename);
    if(!fin.is_open())
    return arr;
    string line;
    
    Date d;
    getline(fin,line,'\n');
    while(!fin.eof())
    {
        General g;
        getline(fin,g.name,',');
        getline(fin,g.nationality,',');
        getline(fin,line,',');
        g.born=SplitDate(line);
        getline(fin,line,',');
        g.death=SplitDate(line);
        getline(fin,line,',');
        g.known_battles=SplitBattle(line);
        getline(fin,line,',');
        getline(fin,line,',');
        getline(fin,line,',');
        getline(fin,line,'\n');
        arr.push_back(g);
    }
    return arr;
}
bool DateCompare(Date a,Date b)
{
    if(a.era=="BC"&&b.era=="AD")return true;
    if(b.era=="BC"&&a.era=="AD")return false;
    if(a.era=="BC"&&b.era=="BC")
    {
        if(a.year<b.year)return true;
        if(a.year>b.year)return false;
        if(a.month>b.month)return true;
        if(a.month>b.month)return false;
        if(a.day>b.day)return true;
        if(a.day>b.day)return false;
    }
    if(a.era=="AD"&&b.era=="AD")
    {
        if(a.year>b.year)return true;
        if(a.year<b.year)return false;
        if(a.month>b.month)return true;
        if(a.month>b.month)return false;
        if(a.day>b.day)return true;
        if(a.day>b.day)return false;
    }
}
Node* CreateNode(General g)
{
    Node* n= new Node;
    n->general=g;
    n->left=nullptr;
    n->right=nullptr;
    return n;
}
Node* InsertNode(Node* p,General g)
{
    if(p==nullptr)
    {CreateNode(g);
    return 0;}
    if(DateCompare(p->general.born,g.born))
        InsertNode(p->right,g);
    if(DateCompare(g.born,p->general.born))
        InsertNode(p->left,g);
    if(equaldate(p->general.born,g.born))
    {
        if(DateCompare(p->general.death,g.death))
        InsertNode(p->right,g);
    if(DateCompare(g.death,p->general.death))
        InsertNode(p->left,g);
    }
}
Node* prob2(vector<General> generals)
{
    int c=generals.size();
    Node* proot=CreateNode(generals[0]);
    for(int i=1;i<c;i++)
    {
        InsertNode(proot,generals[i]);
    }
    return proot;
} // return the root node of the tree.
bool equaldate(Date a,Date b)
{
    if(a.era=="BC"&&b.era=="BC")
    {
        if(a.year==b.year&&a.month==b.month&&a.day==b.day)return true;
    }
    if(a.era=="AD"&&b.era=="AD")
    {
        if(a.year==b.year&&a.month==b.month&&a.day==b.day)return true;
    }
    return false;
}
int prob3(Node* root, string born_year)
{
    Date d=SplitDate(born_year);
    int c=0;
    
}