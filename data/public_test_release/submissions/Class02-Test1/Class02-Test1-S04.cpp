#include <iostream>
#include <sstream>
#include <fstream>
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

struct Date {
    int day, month, year;
};

int countLine(const string& filename) {
    ifstream in(filename);
    if (!in.is_open()) {
        cout << "Cant open file " << filename << endl;
        return 0;
    }

    string line;
    getline(in, line);

    int cnt = 0;
    while(getline(in, line)) {
        cnt++;
    }
    return cnt;

}

Date processDate(string input) {
    if (input.empty()) return {0, 0, 0};

    stringstream ss(input);
    string token;

    Date d;
    getline(ss, token, '-');
    d.day = !token.empty() ? stoi(token) : 0;

    getline(ss, token, '-');
    d.month = !token.empty() ? stoi(token) : 0;

    getline(ss, token);
    d.year = !token.empty() ? stoi(token) : 0;
    
    return d;
}

string* processInnerList(const string& input, int& n) {
    if (input.empty()) return nullptr;

    string* res = new string[10];
    
    stringstream ss(input);
    string token;
    int i = 0;
    while(getline(ss, token, ';') && i < n) {
        res[i] = token;
        i++;
    }
    n = i;
    return res;
}

Battle* prob1(string filename, int& n) {
    ifstream in(filename);
    if (!in.is_open()) {
        cout << "Cant open file " << filename << endl;
    }

    int size = countLine(filename);
    Battle* list = new Battle[size];

    int i = 0;
    stringstream ss(filename);
    string line;

    getline(ss, line);

    while(getline(ss, line) && i < size) {
        Battle b;
        getline(ss, b.name, ',');
        getline(ss, b.location, ',');

        getline(ss, b.from_date, ',');
        getline(ss, b.to_date, ',');

        string token;
        getline(ss, token, ',');

        getline(ss, token, ',');
        
        getline(ss, token);
        b.list_famous_generals = processInnerList(token, b.total_famous_generals);

        list[i] = b;
        i++;
    }
    return list;
}

Node* createNode(const Battle& b) {
    Node* newNode = new Node();
    newNode->battle = b;
    newNode->next = nullptr;
    return newNode;
}

void addTail(Node*& head, const Battle& b) {
    Node* newNode = createNode(b);
    if (head == nullptr) {
        head = newNode;
    }

    Node* tmp = head;
    while(tmp->next) {
        tmp = tmp->next;
    }
    tmp->next = newNode;
}

Node* prob2(Battle* battles, int n) {
    if (battles == nullptr || n < 0) return nullptr;

    Node* head = nullptr;

    int i = 0;
    while (head) {
        addTail(head, battles[i]);
        i++;
    }
    return head;
}

void printList(Node* head) {
    Node* curr = head;
    int k = 0;
    while (curr) {
        Battle b;
        b = curr->battle;
        cout << b.name << ' ' << b.location << ' ' << b.from_date << ' ' << b.to_date;
        for (int i = 0; i < b.total_famous_generals; i++) {
            cout << b.list_famous_generals[i] << ';';
        }
        curr = curr->next;
        k++;
    }
}


int prob3(Node* head, string start_year, string end_year);
void prob4(Node*& head, string general);

int main() {
    string filename = "50-european-battles-first-20.csv";
    int size = countLine(filename);
    cout << size << endl;
    Battle* b = prob1(filename, size);
    Node* head = prob2(b, size);

    printList(head);

    return 0;
}