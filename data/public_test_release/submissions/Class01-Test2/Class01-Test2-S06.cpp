#include<iostream>
#include<sstream>
#include<string>
#include<fstream>
#include<algorithm>
#include<vector>
using namespace std;
struct Date {
int day, month, year;
string era; // AD or BC
};
struct General {
string name, nationality;
Date born, death;
vector<string> known_battles;
};
struct Node {
General general;
Node* left;
Node* right;
};
Date splitdate(string s)
{
    Date d;
    stringstream ss;
    for(int i = 0; i < s.length(); i++)
    {
        if(s[i] == '-')
        s[i] = ' ';
    }
    ss << s;
    ss >> d.day >> d.month >> d.year >> d.era;
    return d;
}
vector<string> splitstring(string s)
{
    vector<string> ds;
    stringstream ss(s);
    string token;
    while(getline(ss, token, '|'))
    {
        ds.push_back(token);
    }
    return ds;
}
vector<General> prob1(string filename)
{
    vector<General> ds;
    ifstream file(filename);
    if(!file.is_open())
    {
        cout << "Khong the mo file";
        return;
    }
    string line;
    getline(file, line);
    while(getline(file, line))
    {
        if(line.empty() || line == "\r")
        {
            continue;
        }
        stringstream ss(line);
        string token[4];
        for(int i = 0; i < 5; i++)
        {
            getline(ss, token[i], ',');
        }
        General g;
        g.name = token[0];
        g.nationality = token[1];
        g.born = splitdate(token[2]);
        g.death = splitdate(token[3]);
        g.known_battles = splitstring(token[4]);
        ds.push_back(g);
    }
    file.close();
    return ds;
}
int prob3(Node* root, string born_year)
{
    int year = stoi(born_year);
    int count = 0;
    if(root == NULL)
    {
        return 0;
    }
    if(root->general.born.era == born_year && root->general.born.year == year)
    {
        count++;
    }
    else if(root->general.born.era < born_year)
    {
        prob3(root->right, born_year);
    }
    else if(root->general.born.era > born_year)
    {
        prob3(root->left, born_year);
    }
    return count;
}
Node* createnode(General g)
{
    Node* nn = new Node;
    nn->general = g;
    nn->left = NULL;
    nn->right = NULL;
    return nn;
}
void insert(Node *&root, Date born)
{
    if(root == NULL)
    {
        return;
    }
    if(born.era == "AD")
    {
        if(root->general.born.year > born.year)
        {
            insert(root->left, born);
        }
        else
        insert(root->right, born);
    }
    if(born.era == "BC")
    {
        if(root->general.born.year > born.year)
        {
            insert(root->right, born);
        }
        else
        insert(root->right, born);
    }
}
Node* prob2(vector<General> generals)
{

}
Node* findminright(Node *root)
{
    if(root == NULL)
    {
        return NULL;
    }
    while(root->left != NULL)
    {
        root = root->left;
    }
    return root;
}
void prob4(Node*& root, string battle)
{

}