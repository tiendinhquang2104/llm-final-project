#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>
using namespace std;
struct Date { int day, month, year; string era; };
struct General { string name, nationality; Date born, death; vector<string> known_battles; };
struct Node { General general; Node* left; Node* right; };
Date parse(string s) { Date d; stringstream ss(s); string t; getline(ss, t, '-'); d.day = stoi(t);
    getline(ss, t, '-'); d.month = stoi(t); ss >> d.year >> d.era; return d; }
vector<General> prob1(string filename) {
    ifstream f(filename.c_str()); string line; vector<General> v; getline(f, line);
    while (getline(f, line)) { if (line.empty()) continue; General g; stringstream ss(line); string b, d, kb;
        getline(ss, g.name, ','); getline(ss, g.nationality, ','); getline(ss, b, ','); getline(ss, d, ',');
        getline(ss, kb, ','); g.born = parse(b); g.death = parse(d); stringstream ks(kb); string x;
        while (getline(ks, x, '|')) g.known_battles.push_back(x); v.push_back(g); }
    return v;
}
long key(const Date& d) { long y = d.era == "BC" ? -d.year : d.year; return y * 10000 + d.month * 100 + d.day; }
bool lessg(const General& a, const General& b) { if (key(a.born) != key(b.born)) return key(a.born) < key(b.born); return key(a.death) < key(b.death); }
Node* insert(Node* r, const General& g) { if (!r) { Node* x = new Node; x->general = g; x->left = x->right = NULL; return x; }
    if (lessg(g, r->general)) r->left = insert(r->left, g); else r->right = insert(r->right, g); return r; }
Node* prob2(vector<General> gs) { Node* r = NULL; for (size_t i = 0; i < gs.size(); i++) r = insert(r, gs[i]); return r; }
int prob3(Node* r, string y) { if (!r) return 0; stringstream ss(y); int yr; string era; ss >> yr >> era;
    return (r->general.born.year == yr && r->general.born.era == era) + prob3(r->left, y) + prob3(r->right, y); }
bool has(const General& g, string b) { for (size_t i = 0; i < g.known_battles.size(); i++) if (g.known_battles[i] == b) return true; return false; }
void removeNode(Node*& r) { Node* x = r;
    if (!r->left) { r = r->right; delete x; } else if (!r->right) { r = r->left; delete x; }
    else { Node** m = &r->right; while ((*m)->left) m = &(*m)->left; r->general = (*m)->general; Node* y = *m; *m = y->right; delete y; } }
void prob4(Node*& r, string b) { if (!r) return; prob4(r->left, b); prob4(r->right, b); while (r && !has(r->general, b)) removeNode(r); }
