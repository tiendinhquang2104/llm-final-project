#include <iostream>
#include<fstream>
#include <string>
#include <vector>
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

int countLine(string filename){
    fstream fin;
    int n = 0;
    fin.open(filename);
    string line;
    getline(fin,line);
    while (getline(fin,line))
    {
        ++n;
    }
    fin.close();
    return n;
}

Date toDate(string s){
    Date person;
    int space = s.find(' ');
    person.era = s.substr(space+1);
    int first = s.find('-');
    int last = s.find(first+1,'-');
    person.day = stoi(s.substr(0,first));
    person.month = stoi(s.substr(first+1,last-first-1));
    person.year = stoi(s.substr(last+1,space-last-1));
    return person;
}

vector <string> split(string s){
    vector <string> a;
    string line = "";
    for (int i = 0; i < s.size(); i++)
    {
        if (s[i] == '|')
        {
            a.push_back(line);
            line = "";
        }
        else
            line += s[i];
    }
    a.push_back(line);
    return a;
}
//Name,Nationality,Born,Death,KnownBattles,ListOfMedals,KnownPosition,LastPosition,TotalWonBattles

vector<General> prob1(string filename){
    vector<General> G;
    fstream fin;
    int n = countLine(filename);
    fin.open(filename);
    string line;
    getline(fin,line);
    for (int i = 0; i < n; i++)
    {
        General g;
        getline(fin,line,',');
        g.name = line;
        getline(fin,line,',');
        g.nationality = line;
        getline(fin,line,',');
        g.born = toDate(line);
        getline(fin,line,',');
        g.death = toDate(line);
        getline(fin,line,',');
        g.known_battles = split(line);

        getline(fin,line,',');
        getline(fin,line,',');
        getline(fin,line,',');
        getline(fin,line);
        G.push_back(g);
    }
    fin.close();
    return G;
}

struct Node {
General general;
Node* left;
Node* right;
};

Node* createNode(General g){
    Node* p = new Node;
    p->general = g;
    p->left = NULL;
    p->right = NULL;
    return p;
}
// 09-08-1157 AD
void insert(Node* &root,General g){
    if (root == NULL)
    {
        root = createNode(g);
    }
    if (root->general.born.era == "AD" && g.born.era == "AD" || root->general.born.era == "BC" && g.born.era == "BC")
    {
        //g.born.day < root->general.born.day && g.born.month < root->general.born.month && g.born.year < root->general.born.year
        if (g.born.year < root->general.born.year)
        {
            insert(root->left,g);
        }
        else if (g.born.year > root->general.born.year)
        {
            insert(root->right,g);
        }
        else if (g.born.year == root->general.born.year)
        {
            if (g.born.month < root->general.born.month)
            {
                insert(root->left,g);
            }
            else if (g.born.month > root->general.born.month)
            {
                insert(root->right,g);
            }
            else if (g.born.month == root->general.born.month)
            {
                if (g.born.day < root->general.born.day)
                {
                    insert(root->left,g);
                }
                else if (g.born.day > root->general.born.day)
                {
                    insert(root->right,g);
                }
                else if (g.born.day == root->general.born.day)
                {
                    if (g.death.year < root->general.death.year)
                    {
                        insert(root->left,g);
                    }
                    else if (g.death.year > root->general.death.year)
                    {
                        insert(root->right,g);
                    }
                    else if (g.death.year == root->general.death.year)
                    {
                        if (g.death.month < root->general.death.month)
                        {
                        insert(root->left,g);
                        }
                        else if (g.death.month > root->general.death.month)
                        {
                        insert(root->right,g);
                        }
                        else if (g.death.month == root->general.death.month)
                        {
                            if (g.death.day < root->general.death.day)
                            {
                            insert(root->left,g);
                            }
                            else if (g.death.day > root->general.death.day)
                            {
                            insert(root->right,g);
                            }
                        }
                    }
                }
            }
        }
    }
    else if (g.born.era == "BC" && root->general.born.era == "AD")
    {
        insert(root->left,g);
    }
    else if (g.born.era == "AD" && root->general.born.era == "BC")
    {
        insert(root->right,g);
    }
}

Node* prob2(vector<General> generals){
    Node* root = NULL;
    for (int i = 0; i < generals.size(); i++)
    {
        insert(root,generals[i]);
    }
    return root; 
} // return the root node of the tree.

int prob3(Node* root, string born_year){
    if (root == NULL)
    {
        return 0;
    }
    int l = prob3(root->left,born_year);

    int mid = 0;
    int yearFind = stoi(born_year);
    if (root->general.born.year == yearFind)
    {
        mid = 1;
    }
    
    int r = prob3(root->right,born_year);
    return l + mid + r;
}
Node* findmin(Node* root){
    if (root == NULL)
    {
        return NULL;
    }
    while (root->left != NULL)
    {
        root = root->left;
    }
    return root;
}
void prob4(Node*& root, string battle){
    if (root == NULL)
    {
        return;
    }
    prob4(root->left,battle);
    for (int i = 0; i < root->general.known_battles.size(); i++)
    {
        if (root->general.known_battles[i] == battle )
        {
            if (root->left == NULL && root->right == NULL)
            {
                delete root;
                root = NULL;
            }
            else if (root->left == NULL)
            {
                Node* temp = root;
                root = root->right;
                delete temp;
            }
            else if (root->right == NULL)
            {
                Node* temp = root;
                root = root->left;
                delete temp;
            }
            else
            {
                Node* temp = findmin(root->right);
                root->general = temp->general;
                prob4(root->right,battle);
            }
        }
    }
    prob4(root->right,battle);    
}

int main(){
    string filename = "50-best-european-generals-cleaned-first-20.csv";
    vector<General> G = prob1(filename );
    return 0;
}