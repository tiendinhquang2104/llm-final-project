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
string era; // AD or BC
};

struct General {
string name, nationality;
Date born, death;
vector<string> known_battles;
};

int countline(string filename) {
    ifstream fin(filename);
    if (!fin) return 0;

    string line;
    int count = 0;

    while (getline (fin, line)) {
        count++;
    }
    fin.close();
    return count;
}

vector<General> prob1(string filename) {
    ifstream fin(filename);
    vector<General> generals;
    if(!fin) return generals;

    string line;
    int count = countline(filename);

    Date* death = new Date;
    Date* born = new Date;
    General* arr = new General[count];
    

    for (int i = 0; i < count; i++) {
        getline(fin, arr[i].name, ',');
        getline(fin, arr[i + 1].nationality, ',');
        cin >> born[i].day >> born[i+1].month>> born[i+2].year >> born[i+3].era;
        cin >>death[i].day >> death[i+1].month>> death[i+2].year >> death[i+3].era;

        // vector<string> vector1;
        // for (int i = 0; i < count; i++) {
        //     vector1.push_back(arr[i]);
        // }


    }
    return generals;
}

struct Node {
General general;
Node* left;
Node* right;
};

Node* prob2(vector<General> generals) {
    Node* pRoot = new Node;
    for (int i = 0; i < 21; i++  ) {
        if (pRoot == NULL) return pRoot;
    }



    return pRoot;
}

// int prob3(Node* root, string born_year) {

// }

// void prob4(Node*& root, string battle) {

// }
int main () {
   

}