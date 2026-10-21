#include <iostream>
#include <fstream>
#include <string>
#include <sstream>
#include <cstring>
#include <cmath>
using namespace std;

//Problem 1

struct Battle {
     string name, location;
     string from_date, to_date;
     int total_famous_generals;
     string *list_famous_generals;
};

int countline(string fileName){
    int n = 0;
    ifstream fs(fileName);
    string tmp;
    getline(fs, tmp);
    while (getline(fs, tmp, '\n')){
        if (!tmp.empty()){
            n++;
        }
    }
    fs.close();
    return n;
}

int total_general(string line){
    int num = 0;
    stringstream ss(line);
    string tmp;
    while (getline(ss, tmp, ';')){
        num++;
    }
    return num;
}

string *ToList(string line){
    int n = total_general(line);
    string *result = new string[n];
    stringstream ss(line);
    for (int i = 0; i < n; i++){
        getline(ss, result[i], ';');
    }

    return result;
}

Battle split_line(string line){
    Battle result;
    stringstream ss(line);
    string tmp;
    getline(ss, tmp, ','); result.name = tmp;
    getline(ss, tmp, ','); result.location = tmp;
    getline(ss, tmp, ','); result.from_date = tmp;
    getline(ss, tmp, ','); result.to_date = tmp;
    getline(ss, tmp, ',');
    getline(ss, tmp, ',');
    getline(ss, tmp, '\n'); 
    result.total_famous_generals = total_general(tmp);
    result.list_famous_generals = ToList(tmp);
    return result;
}

Battle *prob1(string fileName, int &n){
    Battle *Battles = new Battle[n];
    ifstream fs(fileName);
    string tmp;
    getline(fs, tmp, '\n');
    for (int i = 0; i < n; i++){
        getline(fs, tmp,'\n');
        Battles[i] = split_line(tmp);
    }
    fs.close();
    return Battles;
}


// Problem 2
struct Node {
    Battle battle;
    Node *next;
};

Node *makeNode (Battle x){
    Node *newNode = new Node;
    newNode->battle = x;
    newNode->next = NULL;
    return newNode;
}
void addTail(Node *&head, Battle x){
    Node *newNode = makeNode(x);
    if (head == NULL){
        head = newNode;
        return;
    }

    Node *tmp = head;
    while (tmp->next != NULL){
        tmp = tmp->next;
    }

    tmp->next = newNode;
}
Node *prob2 (Battle *battles, int n){
    Node *result = NULL;
    for (int i = 0; i < n; i++){
        addTail(result, battles[i]);
    }

    return result;
}

// Problem 3
int ToYear(string line){
    int year = 0;
    stringstream ss(line);
    string tmp;
    getline(ss, tmp, '-');
    getline(ss, tmp, '-');
    getline(ss, tmp);
    year = stoi(tmp);
    return year;
}
int prob3(Node *head, string start_year, string end_year){
    int result = 0;
    while (head != NULL){
        int year_start = ToYear(head->battle.from_date);
        int year_end = ToYear(head->battle.to_date);
        if (stoi(start_year) <= year_start && year_end <= stoi(end_year)){
            result++;
        }
        head = head->next;
    }

    return result;
}


// Problem 4

void deleteNode(Node *&head, Node *&target){
    if (head == target){
        head = head->next;
        delete target;
        return;
    }

    Node *tmp = head;

    while (tmp->next != target){
        tmp = tmp->next;
    }

    tmp->next = target->next;
    delete target;
}

void prob4(Node *&head, string general){
    Node *tmp = head;
    while (tmp != NULL){
        for (int i = 0; i < tmp->battle.total_famous_generals; i++){
            if (tmp->battle.list_famous_generals[i] == general){
                Node *tmp2 = tmp;
                tmp = tmp->next;
                deleteNode(head, tmp2);
                continue;
            }
        }
        tmp = tmp->next;    
    }
}



//"50-european-battles-first-20.csv"