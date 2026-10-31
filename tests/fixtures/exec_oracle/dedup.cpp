#include <iostream>
#include <set>
#include <vector>
using namespace std;
int main() { int n; cin >> n; vector<long long> a(n), k; set<long long> s;
    for (int i = 0; i < n; i++) { cin >> a[i]; if (s.insert(a[i]).second) k.push_back(a[i]); }
    cout << k.size() << endl; for (size_t i = 0; i < k.size(); i++) cout << (i ? " " : "") << k[i]; cout << endl; }
