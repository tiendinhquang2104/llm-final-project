#include <iostream>
#include <fstream>
#include <sstream>
#include <vector>
#include <string>
using namespace std;
struct Date{
    int day, month, year;
    string era;
};
struct General{
    string name, nationality;
    Date born, death;
    vector<string> known_battles;
};
struct Node{
    General key;
    Node* left;
    Node* right;
};
Node* prob2(General g){
    Node* newNode = new Node;
    newNode->key=g;
    newNode->left=nullptr;
    newNode->right=nullptr;
    return newNode;
}
vector<General> prob1(string filename){
    vector<General> g_list;
    ifstream fin(filename);
    if(!fin.is_open()) {
        cout << "Loifile";
    }
    string line;
    General G;
    getline(fin, line);
    while(getline(fin, line)){
        stringstream ss(line);
        getline(ss, G.name, ',');
        getline(ss, G.nationality, ',');
    }
    fin.close();
    g_list.push_back(G);
    return g_list;
}
void insertBST(Node*& root, vector<General> g){
    if(root == nullptr){
        root = prob2(g);
        return;
    }
    if(root->left<root->key) insertBST(left, g);
    if(root->right>root->key) insertBST(right, g);
}
void LNR(Node* pRoot){
    if(pRoot==nullptr) return;
    cout << 
    pRoot->left;
    pRoot->right;

}
void  prob4(Node*& root, string battle){

}


int main(){
    string filename = "50-best-european-generals-cleaned-first-20.csv";
    vector<General> arr = prob1(filename);
    Node* root = nullptr;
    for(int i=0;i<arr.size();i++){
        insertBST(root, arr[i]);
    }
    LNR(root);
    return 0;
}