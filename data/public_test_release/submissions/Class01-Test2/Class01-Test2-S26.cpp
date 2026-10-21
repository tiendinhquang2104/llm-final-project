#include <iostream>
#include <fstream>
#include <vector>
#include <sstream>
#include <string>
#include <cstring>
#include <cmath>
using namespace std;

struct Date {
    int day, month, year;
    string era;
};
struct General {
    string name, nationality;
    Date born, death;
    vector<string> known_battles;
};

//Problem 1:
struct Node {
    General general;
    Node* left;
    Node* right;
};

vector<General> prob1(string filename) {

}

//Problem 2:
Node* prob2(vector<General> generals) {

}

//Problem 3:
int prob3 (Node* root, string born_year) {

}

//Problem 4:
void prob4 (Node*& root, string battle) {

}