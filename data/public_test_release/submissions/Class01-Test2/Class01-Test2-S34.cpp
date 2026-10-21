#include <iostream>
#include <string>
#include <string.h>
#include <vector>
#include <istream>

using namespace std;

struct Node {
    Node* next;
    General key;
};

struct Date {
    int day, month, year;
    string era;
};

struct General {
    string name, nationality;
    Date born, death;
    vector<string> known_battles;
};

vector<General> prob1(string filename) {
}

int main() {

    return 0;
}


