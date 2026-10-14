#include <iostream>
#include <fstream>
#include <algorithm>
#define ll long long
using namespace std;

struct Rec { int a, b; };

Rec* prob1(string filename, int& n) {
    ifstream in(filename);
    Rec* a = new Rec[1000];
    n = 0;
    while (in >> a[n].a >> a[n].b) n++;
    return a;
}

int prob2(Rec* a, int n) { return n; }

int prob3(Rec* a, int n) {
    int r = a[0].b;
    for (int i = 1; i < n; i++) r = min(r, a[i].b);
    return r;
}

void prob4(Rec* a, int n) { cout << prob2(a, n); }
