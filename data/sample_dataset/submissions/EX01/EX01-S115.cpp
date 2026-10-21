#include<iostream>
#include<string>
#include<fstream>
using namespace std;
struct Date {
    int day, month, year;
    string era; // AD or BC
};
struct General {
    string name, nationality;
    Date born, death;
    int total_known_battles;
    string* known_battles;
};
struct Node {
    General general;
    Node* next;
};
int cntLine (string filename) {
    int n = 0;
    ifstream fin(filename);
    string line = "";
    getline(fin, line);
    while(getline(fin, line)) n++;
    fin.close();
    return n++;
}
Date splitDate(string date) {
    Date d;
    string word = "";
    int n = 0;
    for (char c : date) {
        if (c != '-' && c != ' ') word += c;
        else {
            if (n == 0) d.day = stoi(word);
            if (n == 1) d.month = stoi(word);
            if (n == 2) d.year = stoi(word);
            word.clear();
            n++;
        }
    }
    d.era = word;
    return d;
}
string* splitB (string line, int &n) {
    n = 1;
    for (char c : line) if (c == '|') n++;
    string* a = new string[n];
    int k = 0;
    string word = "";
    for (char c : line) {
        if (c != '|') word += c;
        else {
            a[k++] = word;
            word.clear();
        }
    }
    a[k++] = word;
    return a;
}
General splitLine(string line) {
    string* a = new string[9];
    string word = "";
    int k = 0;
    for (char c : line) {
        if (c != ',') word += c;
        else {
            a[k++] = word;
            word.clear();
        }
    }
    a[k++] = word;
    General g;
    g.name = a[0];
    g.nationality = a[1];
    g.born = splitDate(a[2]);
    g.death = splitDate(a[3]);
    g.known_battles = splitB(a[4], g.total_known_battles);
    delete[] a;
    return g;

}
General* prob1(string filename, int& n) {
    n = cntLine(filename);
    General* a = new General[n];
    ifstream fin(filename);
    string line = "";
    getline(fin, line);
    int k = 0;
    while(getline(fin, line)) {
        a[k++] = splitLine(line);
    }
    fin.close();
    return a;
}
void pushBack (Node*& head, General g) {
    Node* newNode = new Node;
    newNode->general = g;
    newNode->next = nullptr;
    if (!head) {
        head = newNode;
        return;
    }
    Node* p = head;
    while(p->next) p = p->next;
    p->next = newNode;
}
Node* prob2(General* generals, int n) {
    Node* head = new Node;
    head = nullptr;
    for (int i = 0; i < n; i++) {
        pushBack(head, generals[i]);
    }
    return head;
}
int bornYear(General g) {
    if (g.born.era == "BC") return -g.born.year;
    return g.born.year;
}
int deathYear(General g) {
    if (g.born.era == "BC") return -g.death.year;
    return g.death.year;
}
General prob3(Node* head) {
    Node* p = head;
    Node* bestAge = nullptr;
    int best = -1;
    while (p) {
        int ya = bornYear(p->general);
        int yb = deathYear(p->general);
        int age = yb - ya;
        if (best < age) {
            best = age;
            bestAge = p;
        }
        p = p->next;
    }
    return bestAge->general;
}
void prob4(Node*& head, string nationality) {
    if (!head) return;
    Node* p = head;
    Node* pre = nullptr;
    while(p) {
        if (p->general.nationality == nationality) {
            Node* del = p;
            if (pre == nullptr) {
                p = head->next;
                head = p;
            } else {
                pre->next = p->next;
                p = pre->next;
            }
            delete del;
            del = nullptr;
        } else {
            pre = p;
            p = p->next;
        }
    }
}
int main () {
    int n;
    General* a = prob1("Generals.csv", n);
    /* for (int i = 0; i < n; i++) {
        cout << a[i].name << ' ' << a[i].nationality << ' ' <<  a[i].born.year << ' ' << a[i].death.year << ' ' << a[i].known_battles[0] << ' ' << a[i].total_known_battles << '\n';
    } */
    Node* head = prob2(a, n);
    General g = prob3(head);
    cout << g.name;
    delete[] a;
}