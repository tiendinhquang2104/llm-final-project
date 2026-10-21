#include <iostream>
#include <string>
#include <fstream>
#include <sstream>
using namespace std;

struct Battle {
    string name, location;
    string from_date, to_date;
    int total_famous_generals;
    string* list_famous_generals;
};

struct Node {
    Battle battle;
    Node* next;
};

int countLine(string filename){
    ifstream fin;
    fin.open(filename);

    string line;
    getline(fin, line, '\n');
    int count = 0;
    while(getline(fin, line, '\n')){
        count++;
    }        
    fin.close();
    return count;

}

Battle* prob1(string filename, int& n){
    ifstream fin;
    fin.open(filename);

    n = countLine(filename);
    Battle* result = new Battle[n];
    string line;

    getline(fin, line, '\n');
    int i = 0;
    while (getline(fin, line, '\n')){
        Battle tmp;
        tmp.name = line;

        // getline(fin, line, ',');
        // tmp.location = line;

        // getline(fin, line, ',');
        // tmp.from_date = line;

        // getline(fin, line, ',');
        // tmp.to_date = line;

        // getline(fin, line, ',');
        // tmp.location = line;

        result[i] = tmp;
        i++;
    }

    fin.close();
    return result;
}

Node* createNode(Battle battle){
    Node* p = new Node;
    p->battle = battle;
    p->next = nullptr;
    return p;
}

// Node* prob2(Battle* battles, int n){
//     Node* p = createNode(p);
//     p->battle = head;

//     while (p->next)
    
// }

struct Date{
    int day, month, year;
};

// int prob3(Node* head, string start_year, string end_year){

// }

// int main(){
//     int line = countLine("50-european-battles-first-20-c6.csv");
//     cout << line << endl;
//     Battle* a = prob1("50-european-battles-first-20-c6.csv", line);
//     return 0;
// }