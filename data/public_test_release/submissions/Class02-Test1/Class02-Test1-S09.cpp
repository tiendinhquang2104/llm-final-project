#include <iostream>
#include <fstream>
#include <string>
using namespace std;

struct Battle {
    string name, location;
    string from_date, to_date;
    int total_famous_generals;
    string* list_famous_generals;
};

int countLine (string filename) {
    int count = 0;
    string line;
    ifstream fin(filename);
    getline(fin, line, '\n');
    while (getline(fin, line, '\n')) count++;
    fin.close();
    return count;
}

Battle* prob1(string fileName, int& n) {
    n = countLine(fileName);
    string line;
    int count = 0;
    Battle* ans = new Battle[n];
    ifstream fin(fileName);
    getline(fin, line, '\n');
    for (int i = 0; i < n; i++) {
        getline(fin, ans[i].name, ',');
        getline(fin, ans[i].location,',');
        getline(fin, ans[i].from_date, ',');
        getline(fin, ans[i].to_date, ',');
        
    }
    fin.close();
    return ans;
}

struct Node {
    Battle battle;
    Node* next;
};

void addTail (Node*& head, Battle data) {
    Node* p = new Node;
    p->battle = data;
    p->next = nullptr;

    if (head == nullptr) {
        head = p;
        return;
    }

    if (head->next == nullptr) {
        head->next = p;
        return;
    }

    Node* tmp = head;
    while (tmp->next != nullptr) {
        tmp = tmp->next;
    }
    tmp->next = p;
}

Node* prob2 (Battle* ans, int n) {
    Node* head = nullptr;
    for (int i = 0; i < n; i++) {
        addTail(head, ans[i]);
    }
    return head;
}

void printList(Node*& head) {
    Node* p = head;
    while (p != nullptr) {
        cout << p->battle.name << "|" << p->battle.location << "|" << p->battle.from_date << endl;
        p = p->next;
    }
}

// int prob3(Node* head, string start_year, string end_year) {
    
// }

int main() {
    int n = 0;
    Battle* a = prob1("50-european-battles-first-20.csv", n);
    Node* list = prob2(a, n);
    printList(list);
    delete []a;
    return 0;
}