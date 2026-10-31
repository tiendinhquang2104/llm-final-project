#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
using namespace std;
struct Date { int day, month, year; string era; };
struct General { string name, nationality; Date born, death; int total_known_battles; string* known_battles; };
struct Node { General general; Node* next; };
Date parse(string s) { Date d; stringstream ss(s); string t; getline(ss, t, '-'); d.day = stoi(t);
    getline(ss, t, '-'); d.month = stoi(t); ss >> d.year >> d.era; return d; }
General* prob1(string filename, int& n) {
    ifstream f(filename.c_str()); string line; n = 0; getline(f, line);
    while (getline(f, line)) if (!line.empty()) n++;
    General* a = new General[n]; f.clear(); f.seekg(0); getline(f, line);
    for (int i = 0; i < n; i++) { getline(f, line); stringstream ss(line); string b, d, kb;
        getline(ss, a[i].name, ','); getline(ss, a[i].nationality, ','); getline(ss, b, ','); getline(ss, d, ',');
        getline(ss, kb, ','); a[i].born = parse(b); a[i].death = parse(d);
        int k = 1; for (char c : kb) if (c == '|') k++; a[i].total_known_battles = k; a[i].known_battles = new string[k];
        stringstream ks(kb); for (int j = 0; j < k; j++) getline(ks, a[i].known_battles[j], '|'); }
    return a;
}
Node* prob2(General* g, int n) { Node* h = NULL; Node* t = NULL;
    for (int i = 0; i < n; i++) { Node* x = new Node; x->general = g[i]; x->next = NULL; if (!h) h = x; else t->next = x; t = x; }
    return h; }
int age(const General& g) { int b = g.born.era == "BC" ? -g.born.year : g.born.year;
    int d = g.death.era == "BC" ? -g.death.year : g.death.year; return d - b; }
General prob3(Node* head) { General best = head->general;
    for (Node* p = head->next; p; p = p->next) if (age(p->general) > age(best)) best = p->general; return best; }
void prob4(Node*& head, string nat) {
    while (head && head->general.nationality == nat) { Node* x = head; head = head->next; delete x; }
    for (Node* p = head; p && p->next;) { if (p->next->general.nationality == nat) { Node* x = p->next; p->next = x->next; delete x; } else p = p->next; }
}
