#include<iostream>
#include<vector>
#include<fstream>
#include<math.h>
#include<string>

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

void saveTree(Node* root, vector<Node*> &inorder){
    if(!root) return;
    saveTree(root->left, inorder);
    inorder.push_back(root);
    saveTree(root->right, inorder);
}

Node* buildTree(vector<Node*> &inorder, int l, int r){
    if(l > r) return nullptr;
    int m = l + (r - l)/2;
    Node* root = inorder[m];
    root->left = buildTree(inorder, l, m - 1);
    root->right = buildTree(inorder, m + 1, r);

    return root;
}

Node* balanceTree(Node* root){
    vector<Node*> order;
    saveTree(root, order);
    return buildTree(order, 0, order.size() - 1);
}

Node* creatNode(General x){
    Node* newNode = new Node;
    newNode->general = x;
    newNode->left = nullptr;
    newNode->right = nullptr;

    return newNode;
}

void insertNode(Node* root, General x){
    if(!root){
        root = creatNode(x);
        return;
    }

        if(x.born.era == "BC" && root->general.born.era == "BC"){
            if(x.born.year > root->general.born.year) insertNode(root->left, x);
            else if(x.born.year < root->general.born.year) insertNode(root->right, x);
            else{
                if(x.born.month < root->general.born.month) insertNode(root->left, x);
                else if(x.born.month > root->general.born.month) insertNode(root->right, x);
                else{
                    if(x.born.day < root->general.born.day) insertNode(root->left, x);
                    else if(x.born.day > root->general.born.day) insertNode(root->right, x);
                }
            }
        }
        else if(x.born.era == "AD" && root->general.born.era == "AD"){
            if(x.born.year < root->general.born.year) insertNode(root->left, x);
            else if(x.born.year > root->general.born.year) insertNode(root->right, x);
            else{
                if(x.born.month < root->general.born.month) insertNode(root->left, x);
                else if(x.born.month > root->general.born.month) insertNode(root->right, x);
                else{
                    if(x.born.day < root->general.born.day) insertNode(root->left, x);
                    else if(x.born.day > root->general.born.day) insertNode(root->right, x);
                }
            }
        }
        else if(x.born.era == "BC" && root->general.born.era == "AD"){
            insertNode(root->left, x);
        }
        else if(x.born.era == "AD" && root->general.born.era == "BC"){
            insertNode(root->right, x);
        }
        else{
                if(x.death.era == "BC" && root->general.death.era == "BC"){
                    if(x.death.year > root->general.death.year) insertNode(root->left, x);
                    else if(x.death.year < root->general.death.year) insertNode(root->right, x);
                else{
                    if(x.death.month < root->general.death.month) insertNode(root->left, x);
                    else if(x.death.month > root->general.death.month) insertNode(root->right, x);
                    else{
                        if(x.death.day < root->general.death.day) insertNode(root->left, x);
                        else if(x.death.day > root->general.death.day) insertNode(root->right, x);
                    }
                }
            }
            else if(x.death.era == "AD" && root->general.death.era == "AD"){
                if(x.death.year < root->general.death.year) insertNode(root->left, x);
                else if(x.death.year > root->general.death.year) insertNode(root->right, x);
                else{
                    if(x.death.month < root->general.death.month) insertNode(root->left, x);
                    else if(x.death.month > root->general.death.month) insertNode(root->right, x);
                    else{
                        if(x.death.day < root->general.death.day) insertNode(root->left, x);
                        else if(x.death.day > root->general.death.day) insertNode(root->right, x);
                    }
                }
            }
            else if(x.death.era == "BC" && root->general.death.era == "AD"){
                insertNode(root->left, x);
            }
            else if(x.death.era == "AD" && root->general.death.era == "BC"){
                insertNode(root->right, x);
            }
        }
}

void saveTree(Node* root, vector<Node*> &inorder){
    if(!root) return;
    saveTree(root->left, inorder);
    inorder.push_back(root);
    saveTree(root->right, inorder);
}

Node* buildTree(vector<Node*> &inorder, int l, int r){
    if(l > r) return nullptr;
    int m = l + (r - l)/2;
    Node* root = inorder[m];
    root->left = buildTree(inorder, l, m - 1);
    root->right = buildTree(inorder, m + 1, r);

    return root;
}

Node* balanceTree(Node* root){
    vector<Node*> order;
    saveTree(root, order);
    return buildTree(order, 0, order.size() - 1);
}

int cntLine(string filename){
    int cnt = 0;
    string line = "";
    ifstream fin(filename);
    getline(fin, line);
    while(getline(fin, line)) cnt++;

    fin.close();
    return cnt;
}

Date dat(string line){
    Date d;
    string word = "";
    int cnt = 0;

    for(char c : line){
        if(c != '-' && c != ' ') word += c;
        else{
            if(cnt == 0){
                d.day = stoi(word);
                word.clear();
                cnt += 1;
            }
            else if(cnt == 1){
                d.month = stoi(word);
                word.clear();
                cnt += 1;
            }
            else if(cnt == 2){
                d.year = stoi(word);
                word.clear();
                cnt += 1;
            }
        }
    }
    d.era = word;
    word.clear();

    return d;
}

vector<string> Kbattle(string line){
    vector<string> k;
    string w = "";
    for(char c : line){
        if(c != '|') w += c;
        else{
            k.push_back(w);
            w.clear();
        }
    }

    k.push_back(w);
    w.clear();

    return k;
}

vector<General> prob1(string filename){
    vector<General> g;
    ifstream fin(filename);

    int n = cntLine(filename);
    string line = "";
    getline(fin, line);

    for(int i = 0; i < n; i++){
        General G;
        getline(fin, line, ',');
        G.name = line;

        getline(fin, line, ',');
        G.nationality = line;

        getline(fin, line, ',');
        G.born = dat(line);

        getline(fin, line, ',');
        G.death = dat(line);

        getline(fin, line, ',');
        G.known_battles = Kbattle(line);

        g.push_back(G);

        getline(fin, line, '\n');
    }

    fin.close();

    return g;
}

Node* prob2(vector<General> generals){
    Node* root = nullptr;
    for(int i = 0; i < generals.size(); i++){
        insertNode(root, generals[i]);
    }

    return root;
}

int prob3(Node* root, string born_year){
    if(!root) return 0;
    return prob3(root->left, born_year) + prob3(root->right, born_year) + 1;
}

Node* get(Node* root){ 
    if(!root) return nullptr;
    root = root->right;
    while(root->left) root = root->left;
    return root;
}

void prob4(Node*& root, string battle){
    if(!root) return;
    for(int i = 0; i < root->general.known_battles.size(); i++){
        if(root->general.known_battles[i] != battle){
            prob4(root->left, battle);
            prob4(root->right, battle);
        }
        else{
            if(!root->left){
                Node* tmp = root->right;
                delete root;
                root = tmp;
            }
            else if(!root->right){
                Node* tmp = root->left;
                delete root;
                root = tmp;
            }
            else{
                Node* p = get(root);
                root->general = p->general;
                prob4()
            }
        }
    }

}