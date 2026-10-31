#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
using namespace std;
struct Battle { string name, location; string from_date, to_date; int total_famous_generals; string* list_famous_generals; };
struct Node { Battle battle; Node* next; };
Battle* prob1(string filename, int& n) {
    ifstream f(filename.c_str()); string line; n = 0; getline(f, line);
    while (getline(f, line)) if (!line.empty()) n++;
    Battle* a = new Battle[n]; f.clear(); f.seekg(0); getline(f, line);
    for (int i = 0; i < n; i++) { getline(f, line); stringstream ss(line); string skip, gl;
        getline(ss, a[i].name, ','); getline(ss, a[i].location, ','); getline(ss, a[i].from_date, ',');
        getline(ss, a[i].to_date, ','); getline(ss, skip, ','); getline(ss, skip, ','); getline(ss, gl);
        int k = 1; for (char c : gl) if (c == ';') k++; a[i].total_famous_generals = k; a[i].list_famous_generals = new string[k];
        stringstream ks(gl); for (int j = 0; j < k; j++) getline(ks, a[i].list_famous_generals[j], ';'); }
    return a;
}
Node* prob2(Battle* g, int n) { Node* h = NULL; Node* t = NULL;
    for (int i = 0; i < n; i++) { Node* x = new Node; x->battle = g[i]; x->next = NULL; if (!h) h = x; else t->next = x; t = x; }
    return h; }
int year(string d) { return stoi(d.substr(d.rfind('-') + 1)); }
int prob3(Node* head, string a, string b) { int c = 0, ya = stoi(a), yb = stoi(b);
    for (Node* p = head; p; p = p->next) if (year(p->battle.from_date) >= ya && year(p->battle.from_date) <= yb) c++; return c; }
bool in(const Battle& b, string g) { for (int i = 0; i < b.total_famous_generals; i++) if (b.list_famous_generals[i] == g) return true; return false; }
void prob4(Node*& head, string g) {
    while (head && !in(head->battle, g)) { Node* x = head; head = head->next; delete x; }
    for (Node* p = head; p && p->next;) { if (!in(p->next->battle, g)) { Node* x = p->next; p->next = x->next; delete x; } else p = p->next; }
}
