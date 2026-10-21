#include <iostream>
#include <fstream>
#include <sstream>
#include <string>

using namespace std;

struct Battle {
    string name, location;
    string from_date, to_date;
    int total_famous_generals;
    string* list_famous_generals;
};

struct Node {
    Battle battle;
    Node* next;
};


int countFileLines(string filename) {
    ifstream file(filename);

    if (!file.is_open()) {
        cout << "Unable to open file\n";
        return -1;
    }

    string line;
    getline(file, line);
    int count = 0;
    
    while (getline(file, line)) {
        count++;
    }
    file.close();
    return count;
}


int countTotalGenerals(string& data) {
    int count = 0;
    if (data.empty()) return 0;

    string temp;
    stringstream ss(temp);
    while(getline(ss, temp, ';')) {
        count++;
    }
    return count;
}

string* readGeneralsList(const string& data, int& size) {
    if (data.empty()) {
        size = 0;
        return NULL;
    }

    string* result = new string[20];
    int i = 0;
    string temp;
    stringstream ss(temp);
    while (i < 20) { 
        getline(ss, temp, ';');
        result[i] = temp;
        i++;
    }
    size = i;
    return result;
} 

Battle* prob1(string filename, int& n) {
    ifstream file(filename);

    if (!file.is_open()) {
        cout << "Unable to open file\n";
        return NULL;
    }

    string line;
    getline(file, line);
    Battle* battleList = new Battle[n];
    
   for (int i = 0; i < n; i++) {
    Battle b;
    stringstream ss(line);
    string temp;

    getline(ss, b.name, ',');
    getline(ss, b.location, ',');
    getline(ss, b.from_date, ',');
    getline(ss, b.to_date, ',');
    

    getline(ss, temp, ',');
    getline(ss, temp, ',');

    getline(ss, temp);
    b.list_famous_generals = readGeneralsList(temp, b.total_famous_generals);

    battleList[i] = b;

   }
   file.close();
   return battleList;
}

Node* createNode(const Battle& data) {
    Node* newNode = new Node();
    newNode->battle = data;
    newNode->next = NULL;
    return newNode;
}

void addTail(Node*& pHead, const Battle& data) {
    Node* newNode = createNode(data);
    if (pHead == NULL) {
        pHead = newNode;
    }
    else {
        Node* current = pHead;
        while (current->next != NULL) {
            current = current->next;
        }
        newNode = current->next;
    }
}



void printList(Node*& pHead) {
    if (pHead == NULL) return;
    Node* current = pHead;
    cout << current->battle.name << " " << current->battle.location << " " << current->battle.from_date << " " << current->battle.to_date << " "; 
    for (int i = 0; i < current->battle.total_famous_generals; i++) {
        cout << current->battle.list_famous_generals[i] << ", ";
    }
}