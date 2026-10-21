#include <iostream>
#include <fstream>
#include <string>
#include <sstream>

using namespace std;

const int MAX_ITEMS = 20;

struct Battle {
    string name;
    string location;
    string fromDate;
    string toDate;
    int casualties;

    string countries[MAX_ITEMS];
    int countryCount = 0;

    string general[MAX_ITEMS];
    int generalCount = 0;
};

struct Node {
    Battle data;
    Node* next;
};

struct LinkedList {
    Node* head;
    Node* tail;
};

void initList(LinkedList &l) {
    l.head = l.tail = nullptr;
}

Node* createNode(Battle b) {
    Node* p = new Node;
    p->data = b;
    p->next = nullptr;
    return p;
}

int stringToInt(string s) {
    if (s.empty()) return 0;
    try { return stoi(s); } catch (...) { return 0; }
}

void splitString(string rawString, string outputArr[], int &count) {
    stringstream ss(rawString);
    string segment;
    count = 0;
    while (getline(ss, segment, ';') && count < MAX_ITEMS) {
        outputArr[count] = segment;
        count++;
    }
}

void addHead(LinkedList &l, Battle b) {
    Node* p = createNode(b);
    if (l.head == nullptr) {
        l.head = l.tail = p;
    } else {
        p->next = l.head; 
        l.head = p;
    }
}


void addTail(LinkedList &l, Battle b) {
    Node* p = createNode(b);
    if (l.head == nullptr) {
        l.head = l.tail = p;
    } else {
        l.tail->next = p; 
        l.tail = p;       
    }
}


void insertAfter(LinkedList &l, Node* q, Battle b) {
    if (q == nullptr) return;
    Node* p = createNode(b);
    p->next = q->next; 
    q->next = p;
    if (l.tail == q) {
        l.tail = p;
    }
}

void removeHead(LinkedList &l) {
    if (l.head == nullptr) return;

    Node* p = l.head;      
    l.head = l.head->next;

    if (l.head == nullptr) {
        l.tail = nullptr; 
    }
    delete p; 
}



void removeTail(LinkedList &l) {
    if (l.head == nullptr) return;

    
    if (l.head == l.tail) {
        removeHead(l);
        return;
    }


    Node* p = l.head;
    while (p->next != l.tail) {
        p = p->next;
    }
    delete l.tail;
    l.tail = p;   
    l.tail->next = nullptr; 
}





void printList(LinkedList l) {
    Node* p = l.head;
    if (p == nullptr) {
        cout << "Danh sach rong!\n";
        return;
    }
    cout << "\n--- DANH SACH TRAN DANH ---\n";
    while (p != nullptr) {
        cout << "[" << p->data.name << "] - Thuong vong: " << p->data.casualties << endl;
        p = p->next;
    }
}

void readFile(string fileName, LinkedList &l) {
    ifstream file(fileName);
    if (!file.is_open()) {
        cout << "Khong mo duoc file\n";
        return;
    }
    string line;
    getline(file, line);
    while (getline(file, line)) {
        if (line.empty()) continue;
        stringstream ss(line);
        Battle b;
        string tempC, tempG, tempCas;

        getline(ss, b.name, ',');
        getline(ss, b.location, ',');
        getline(ss, b.fromDate, ',');
        getline(ss, b.toDate, ',');
        
        getline(ss, tempC, ',');
        splitString(tempC, b.countries, b.countryCount);

        getline(ss, tempCas, ',');
        b.casualties = stringToInt(tempCas);

        getline(ss, tempG, ',');
        splitString(tempG, b.general, b.generalCount);

        addTail(l, b);
    }
    file.close();
}

int main() {
    LinkedList list;
    

    initList(list);


    readFile("50-european-battles-first-20.csv", list);
    cout << "1. Sau khi doc file:\n";
    printList(list);


 

    return 0;
}