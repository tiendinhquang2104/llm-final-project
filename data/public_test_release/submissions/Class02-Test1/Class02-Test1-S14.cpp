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

int countLine(string fileName) {
    ifstream fin(fileName);
    if (!fin.is_open()) {
        cerr << "CANNOT OPEN THIS FILE!" << endl;
        return 0;
    }

    string line;
    int count = 0;
    getline(fin, line);

    while(getline(fin, line)) {
        count++;
    }
    fin.close();
    return count;
}

int totalFamousGeneral(string line) {
    int count = 1;
    
    for (char ch : line) {
        if (ch == ';') count++;
    }

    return count;
}

string* listFamousGeneral(string line) {
    int count = totalFamousGeneral(line);

    string* arr = new string[count];
    stringstream ss(line);
    string token;
    int i = 0;
    while(getline(ss, token, ';')) {
        arr[i] = token;
        i++;
    }
    return arr;
}

Battle readBattle(string line) {
    Battle b;
    stringstream ss(line);
    string token;

    getline(ss, token, ',');
    b.name = token;

    getline(ss, token, ',');
    b.location = token;

    getline(ss, token, ',');
    b.from_date = token;

    getline(ss, token, ',');
    b.to_date = token;

    getline(ss, token, ',');
    getline(ss, token, ',');

    getline(ss, token, ',');
    b.total_famous_generals = totalFamousGeneral(token);
    b.list_famous_generals = listFamousGeneral(token);

    return b;

}

Battle* prob1(string filename, int& n) {
    ifstream fin(filename);
    if (!fin.is_open()) {
        cerr << "CANNOT OPEN THIS FILE" << endl;
        return nullptr;
    }

    Battle* arr = new Battle[n];
    string line;

    getline(fin, line);
    int i = 0;
    while (getline(fin, line)) {
        arr[i] = readBattle(line);
        i++;
    }
    fin.close();
    return arr;
}

Node* createNode (Battle data) {
    Node* p = new Node;
    p->battle = data;
    p->next = nullptr;
    return p;
}

void addHead(Node*& head, Battle data) {
    Node* p = createNode(data);
    p->next = head;
    head = p;
}

Node* prob2(Battle* battles, int n) {
    Node* head = nullptr;

    for (int i = 0; i < n; i++) {
        addHead(head, battles[i]);
    }

    return head;
}

int prob3(Node* head, string start_year, string end_year) {
    if (head == nullptr) return 0;

    int count = 0;
    if (start_year != end_year) count++;

    return count;
}

void prob4(Node*& head, string general) {
    Node* curr = head;
    for (int i = 0; i < curr->battle.total_famous_generals; i++) {
        while (curr != nullptr) {
        if (curr->next->battle.list_famous_generals[i] == general) {
            Node* nxt = curr->next;
            curr->next = nxt->next;
            delete nxt;

            curr = curr->next;
        }
        else {
            curr = curr->next;
        }
    }
}
}

int main() {
    int n = countLine("50-european-battles-first-20.csv");
    Battle* ans = prob1("50-european-battles-first-20.csv", n);
    Node* head = prob2(ans, n);
    Node* curr = head;

    int sum = 0;
    while(curr != nullptr) {
        int total = prob3(curr, curr->battle.from_date,curr->battle.to_date);
        sum += total;
        curr = curr->next;
    }
    cout << sum;
    return 0;
}