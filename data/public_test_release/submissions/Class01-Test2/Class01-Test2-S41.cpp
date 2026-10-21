#include<iostream>
#include<fstream>
#include<string>
#include<vector>
using namespace std;
struct Date {
    int day, month, year;
    string era; 
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
Date splitDate(string date) {
    Date d;
    string word = "";
    int k = 0;
    for (char c : date) {
        if (c != '-' && c != ' ') word += c;
        else {
            if (k == 0) d.day = stoi(word);
            else if (k == 1) d.month = stoi(word);
            else if (k == 2) d.year = stoi(word);
            k++;
            word.clear();
        }
    }
    d.era = word;
    return d;
}
vector<string> splitBattle(string line) {
    string word = "";
    vector<string> K;
    for (char c : line) {
        if (c != '|') word += c;
        else {
            K.push_back(word);
            word.clear();
        }
    }
    K.push_back(word);
    return K;
}
General splitLine(string line) {
    string word = "";
    vector<string> words;
    for (char c : line) {
        if (c != ',') word += c;
        else {
            words.push_back(word);
            word.clear();
        }
    }
    words.push_back(word);
    General G;
    G.name = words[0];
    G.nationality = words[1];
    G.born = splitDate(words[2]);
    G.death = splitDate(words[3]);
    G.known_battles = splitBattle(words[4]);
    return G;
}
vector<General> prob1(string filename) {
    vector<General> G;
    string line = "";
    ifstream fin(filename);
    getline(fin, line);
    while(getline(fin, line)) {
        G.push_back(splitLine(line));
    }
    fin.close();
    return G;
}
bool checkOrder(General a, General b) {
    int da = a.born.day, db = b.born.day;
    int ma = a.born.month, mb = b.born.month;
    int ya = a.born.year, yb = b.born.year;
    if (a.born.era == "BC") ya = -ya;
    if (b.born.era == "BC") yb = -yb;

    if (ya != yb) return ya > yb;
    else if (ma > mb) return ma > mb;
    else if (da > db) return da > db;
    return false;
}
Node* createNode(General x) {
    Node* newNode = new Node;
    newNode->general = x;
    newNode->left = newNode->right = nullptr;
    return newNode;
}
Node* InsertBST(Node* root, General G) {
    if (!root) return createNode(G);
    if (checkOrder(root->general, G)) root->left = InsertBST(root->left, G);
    else if (checkOrder(G, root->general)) root->right = InsertBST(root->right, G);
    return root;
}
Node* prob2(vector<General> generals) {
    Node* root = nullptr;
    for (auto v : generals) {
        root = InsertBST(root, v);
    }
    return root;
}
int prob3(Node* root, string born_year) {
    if (!root) return 0;
    string ans = to_string(root->general.born.year) + ' ' + root->general.born.era;
    if (ans == born_year) return 1 + prob3(root->left, born_year) + prob3(root->right, born_year);
    return prob3(root->left, born_year) + prob3(root->right, born_year);
}
void LNR (Node* root) {
    if (!root) return;
    LNR(root->left);
    cout << root->general.name << '\n';
    LNR(root->right);
}
void findOrder(Node* root, vector<General>& ans, string battle) {
    if (!root) return;
    for (auto v : root->general.known_battles) {
        if (v == battle) {
            ans.push_back(root->general);
            break;
        }
    }
    findOrder(root->left, ans, battle);
    findOrder(root->right, ans, battle);
}
bool checkBorn(General a, General b) {
    int da = a.born.day, db = b.born.day;
    int ma = a.born.month, mb = b.born.month;
    int ya = a.born.year, yb = b.born.year;
    if (a.born.era == "BC") ya = -ya;
    if (b.born.era == "BC") yb = -yb;
    if (ya != yb) return ya > yb;
    else if (ma > mb) return ma > mb;
    else if (da > db) return da > db;
    return false;
}
Node* remove(Node* root, General g) {
    if (!root) return nullptr;
    if (checkBorn(root->general, g)) root->left = remove(root->left, g);
    else if (checkBorn(g, root->general)) root->right = remove(root->right, g);
    else {
        if (root->left && root->right) {
            Node* p = root->right;
            while(p->left) p = p->left;
            root->general = p->general;
            root->right = remove(root->right, p->general);
        } else if (root->left) {
             Node* tmp = root->left;
            delete root;
            root = nullptr;
            return tmp;
        } else if (root->right) {
            Node* tmp = root->right;
            delete root;
            root = nullptr;
            return tmp;
        } else {
            delete root;
            root = nullptr;
            return nullptr;
        }
    }
    return root;
}
void prob4(Node*& root, string battle) {
    vector<General> ans;
    findOrder(root, ans, battle);
    for (auto v : ans) {
        root = remove(root, v);
    }
}
int main () {
    vector<General> ans = prob1("General.csv");
    Node* root = prob2(ans);
    prob4(root, "Battle of France");
    LNR(root);
}
