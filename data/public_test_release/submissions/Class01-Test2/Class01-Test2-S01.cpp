#include <iostream>
#include <cstring>
#include <sstream>
#include <vector>
#include <fstream>

using namespace std;

struct Date {
    int day, month, year;
    string era;
};

struct General {
    std::string name, nationality;
    Date born, death;
    vector<string> known_battles;
};

struct Node {
    General general;
    Node* left;
    Node* right;
};


vector<General> prob1(string filename) {
    vector<General> arr;
    ifstream file;
    stringstream ss;

    if(!file.is_open()) {
        cout << "File not found or error";
        return;
    }

    string line;
    cin.getline(ss, line);
    while(line) {
        
    }
}

Node* createNode(General g) {
    Node* newNode = new Node();
    newNode -> general = g;
    newNode -> left = nullptr;
    newNode -> right = nullptr;
    return newNode;
}

void insertNode(General g, Node*& root) {
    if(root == nullptr) {
        return;
    }
    else if(root -> general.born.year == g.born.year) {
        insertNode(root -> left, g);
    } 
}

Node* prob2(vector<General> generals) {
    Node* newNode = new Node();
    for(int i = 0; i < generals.size(); i++) {
        insertNode()
    }
}

int prob3(Node* root, string born_year) {
    int count = 0;
    int
}

void prob4(Node*& root, string battle) {

}

int main() {

    return 0;
}