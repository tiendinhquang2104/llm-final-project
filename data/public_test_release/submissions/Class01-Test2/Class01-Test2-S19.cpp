#include <iostream>
#include <fstream>
#include <vector>
#include <string>
using namespace std;
struct Date {
    int day, month, year;
    string era; // AD or BC
};
struct General {
    string name, nationality;
    Date born, death;
    vector<string> known_battles;
};
struct Node {
    General general;
    Node* left;
    Node* right;
};
int countLine (string filename){
    ifstream file(filename);
    if (!file) return 0;
    string line;
    int cnt = 0;
    while (getline(file, line)) cnt++;
    file.close();
    return cnt;
}
vector<General> prob1(string filename){
    ifstream file(filename);
    int cnt = countLine (filename);
    int n = cnt - 1;
    string line;
    General *a = new General[n];
    for (int i = 0; i < n; i++){
        getline(file, a[i].name, ',');
        getline(file, a[i].nationality, ',');
        cin >> a[i].born.day >> a[i].born.month >> a[i].born.year;
        cin >> a[i].death.day >> a[i].death.month >> a[i].death.year;
        vector<string> known_battles;
    }
}
Node* prob2(vector<General> generals){
}
int prob3(Node* root, string born_year){
}
void prob4(Node*& root, string battle){
}

