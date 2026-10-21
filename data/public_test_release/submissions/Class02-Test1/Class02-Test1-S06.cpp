#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
using namespace std;

//declare struct
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

//declare function
int countWord(const std::string& input);
int countLine(const std::string& fileName);
Node* createNode(const Battle& b) ;
void addTail(Node*& pHead, const Battle& b);
Battle* prob1(string filename, int& n);
Node* prob2(Battle* battles, int n);
int prob3(Node* head, string start_year, string end_year);
// void prob4(Node*& head, string general);

//problem1
int countLine(const std::string& fileName) {
    std::ifstream fileIn(fileName);
    if (!fileIn.is_open()) {
        std::cout << "Can't open file " << fileName << '\n';
        return 0;
    }

    std::string line;
    std::getline(fileIn, line);
    int cnt = 0;

    while (std::getline(fileIn, line))
        ++ cnt;

    fileIn.close();

    return cnt;
}

int countWord(const std::string& input) {
    if (input.empty())
        return 0;

    std::string field;
    std::stringstream ss(input);
    int cnt = 0;

    while (std::getline(ss, field, ';'))
        ++ cnt;

    return cnt;

}

std::string* processList(const std::string& input) {
    if (input.empty()) return nullptr;

    int size = countWord(input);
    std::string* result = new std::string[size];
    int i = 0;
    std::string field;
    std::stringstream ss(input);

    while (std::getline(ss, field, ';')) {
        result[i] = field;
        ++ i;
    }

    return result;
}

Battle* prob1(string filename, int& n) {
    std::ifstream fileIn (filename);
    if (!fileIn.is_open()) {
        std::cout << "Can't open file " << filename << '\n';
        n = 0;
        return nullptr;
    }
    n = countLine(filename);
    Battle* list = new Battle[n];
    int i = 0;

    std::string line;
    std::getline(fileIn, line);

    while (std::getline(fileIn, line)) {
        Battle b;
        std::stringstream ss(line);
        std::getline(ss, b.name, ',');

        std::getline(ss, b.location, ',');

        std::getline(ss, b.from_date, ',');

        std::getline(ss, b.to_date, ',');

        std::string field;
        std::getline(ss, field, ',');
        
        std::getline(ss, field, ',');
        b.total_famous_generals = !field.empty() ? stoi(field) : 0;

        std::getline(ss, field);
        b.list_famous_generals = processList(field);

        list[i] = b;

        ++ i;
    }

    fileIn.close();

    return list;
}

Node* createNode(const Battle& b) {
    Node* newNode = new Node();
    newNode->battle = b;
    newNode->next = nullptr;

    return newNode;
}

void addTail(Node*& pHead, const Battle& b) {
    Node* newNode = createNode(b);
    if (pHead == nullptr) {
        pHead = newNode;
        return;
    }

    Node* pCurr = pHead;
    while (pCurr->next != nullptr) {
        pCurr = pCurr->next;
    }

    pCurr->next = newNode;
}

Node* prob2(Battle* battles, int n) {
    Node* pHead = nullptr;
    int i = 0;
    while (i < n) {
        addTail(pHead, battles[i]);
        ++ i;
    }
    return pHead;
}

int prob3(Node* head, string start_year, string end_year) {
    if (head == nullptr) return 0;
    int cnt = 0;

    Node* pCurr = head;
    while (pCurr != nullptr) {
        if (pCurr->battle.from_date >= start_year && pCurr->battle.to_date <= end_year)
            ++ cnt;
        pCurr = pCurr->next;
    }

    return cnt;
}

void prob4(Node*& head, string general) {
    if (head == nullptr) return;
    Node* pPrev = nullptr;
    Node* pCurr = head;
    int i = 0;
    while (pCurr != nullptr) {
        Node* tmp = pCurr;
        bool isFound = false;
        for (int i = 0; i < 10; i ++) {
            if (pCurr->battle.list_famous_generals[i] == general) {
                isFound = true;
                break;
            }
        }
        if (isFound) {
            if (pPrev == nullptr) {
                    head = head->next;
                    pCurr = head;
                }

            else {
                pPrev = pCurr->next;
                pCurr = pCurr->next;
            }

            delete tmp;
        }

        else {
            pPrev = pCurr;
            pCurr = pCurr->next;
        }
    }
}
