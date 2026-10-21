#include<iostream>
#include<fstream>
#include<string>
#include<vector>
#include<sstream> 
#include<cstring>
#include<cmath>
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

int countLines(string filename){
    ifstream fin (filename);

    if(!fin) {
        cerr << "cannot open file to count";
        return -1;
    }

    string line;
    int cnt = 0;

    while(getline(fin, line)){
        ++cnt;
    }
    fin.close();

    return (cnt != 0) ? cnt - 1 : 0;
}

void spilitFields(string line, string * fields){
    string field = "";
    int idx = 0;

    for(int i = 0; i < line.length(); ++ i){
        if(line[i] == ','){
            fields[idx++] = field;
            field = "";
        }
        else{
            field += line[i];
        }
    }
    fields[idx] = field;
}

Date readDate(string line){
    string fields[4];
    string field = "";
    int idx = 0;

    for(int i = 0; i < line.length(); ++ i){
        if(line[i] == '-' || line[i] == ' '){
            fields[idx++] = field;
            field = "";
        }
        else{
            field += line[i];
        }
    }
    fields[idx] = field;

    Date d;
    d.day = stoi(fields[0]);
    d.month = stoi(fields[1]);
    d.year = stoi(fields[2]);
    d.era = fields[3];
    
    return d;
}

vector<string> readBattles(string line){
    vector<string> battles;

    string field = "";
    int idx = 0;

    for(int i = 0; i < line.length(); ++ i){
        if(line[i] == '|'){
            battles.push_back(field);
            field = "";
        }
        else{
            field += line[i];
        }
    }
    battles.push_back(field);

    return battles;
}


General readGeneral(string line){
    string fields[9];  

    spilitFields(line, fields);

    General g;
    g.name = fields[0];
    g.nationality = fields[1];
    g.born = readDate(fields[2]);
    g.death = readDate(fields[3]);
    g.known_battles = readBattles(fields[4]);

    return g;
}

vector<General> prob1(string filename){
    vector<General> vt;

    ifstream fin (filename);

    if(!fin) {
        cerr << "cannot open file to read";
        return {};
    }

    string line;
    int cnt = countLines(filename);

    getline(fin, line);

    while(getline(fin, line)){
        vt.push_back(readGeneral(line));
    }

    fin.close();

    return vt;
}
Node * CreateNode(General g){
    return new Node{g, nullptr, nullptr};
}
Node * InsertNode(Node*& pRoot, General g){
    if(!pRoot){
        pRoot = CreateNode(g);
        return pRoot;
    }

    if((pRoot->general.born.era == g.born.era) && (pRoot -> general.born.year > g.born.year)){
        return InsertNode(pRoot -> left, g);
    }
    else return InsertNode(pRoot -> right, g);
}

Node* prob2(vector<General> generals){
    Node * pRoot = nullptr;
    for(int i = 0; i < generals.size(); ++i){
        InsertNode(pRoot, generals[i]);
    }
    return pRoot;
}

int prob3(Node* root, string born_year){
    if(!root) return 0;

    string g_born_year = to_string(root ->general.born.year)  + " " + root->general.born.era;
    if(g_born_year == born_year){
        return 1 + prob3(root -> left, born_year) + prob3(root -> right, born_year);
    }
    else return prob3(root -> left, born_year) + prob3(root -> right, born_year);
}
// Remove all generals that are not participated in a given battle from the BST in Problem 2. In case a node
// has two children, the replacement node will be the leftmost node in the right subtree. You must remove nodes
// in-place (i.e., without using extra lists, arrays, or trees).

Node* findMin(Node* pRoot){
    if(!pRoot) return nullptr;

    while(pRoot -> left){
        pRoot = pRoot -> left;
    }

    return pRoot;
}
void removeMinRight(Node*pRoot){
    if(!pRoot) return;

    while(pRoot -> left){
        pRoot = pRoot -> left;
    }

    delete pRoot;
    pRoot = nullptr;
}


void removeNode(Node* &pRoot){
    if(!pRoot){
        return;
    }

    // leaf
    if(!pRoot -> left && !pRoot ->right){
        delete pRoot;
        pRoot = nullptr;
        return;
    }

    //1 node
    if(pRoot -> left && !pRoot ->right){
        Node * pTemp = pRoot ->left;
        delete pRoot;
        pRoot = pTemp;
        return;
    }
    if(!pRoot -> left && pRoot ->right){
        Node * pTemp = pRoot ->right;
        delete pRoot;
        pRoot = pTemp;
        return;
    }
    // 2 node
    else{
        Node* minRight = findMin(pRoot ->right);

        pRoot -> general = minRight -> general;

        removeMinRight(pRoot -> right);

        return;
    }
}
void prob4(Node*& root, string battle){

}

int main(){
    cout << "Hello";

    string filename = "50-best-european-generals-cleaned-first-20.csv";

    cout << "Count Lines: " << countLines(filename);

    Date d = readDate("09-08-1157 AD");
    cout << endl << d.year << " " << d.era << endl;

    General g = readGeneral("Richard the Lionheart,England,09-08-1157 AD,04-06-1199 AD,Siege of Acre|Battle of Arsuf|Battle of Jaffa,None (King),King of England,King of England,10");

    cout << g.name << " " << g.known_battles[1];

    string g_born_year = to_string(g.born.year)  + " " + g.born.era;
    cout << endl << g_born_year;
}
