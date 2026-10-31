#include <iostream>
#include <string>
using namespace std;
int main() { string f, l; cin >> f >> l; string best = f.substr(0, 1) + l[0];
    for (size_t k = 2; k <= f.size(); k++) { string c = f.substr(0, k) + l[0]; if (c < best) best = c; } cout << best << endl; }
