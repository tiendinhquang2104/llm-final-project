#include <iostream>
#include <fstream>
#include <sstream>
#include <cstring>
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

int toint(string s)
{
    return stoi(s);
}

Battle* prob1(string filename, int& n)
{
    ifstream fin; 
    fin.open(filename);

    if (!fin.is_open()) return nullptr;

    string line; 
    getline(fin,line);

    string s[n] = new string;

    while(getline(fin,line))
    {
        stringstream ss(line);
        string temp; 
        Battle b;

        getline(ss, temp, ',');
        s[n] += temp;
        getline(ss, temp, ',');
        s[n] += temp;
        getline(ss, temp, ',');
        s[n] += temp;
        getline(ss, temp, ',');
        s[n] += temp;
        getline(ss, temp, ',');
        s[n] += temp;
        getline(ss,temp,',');
        s[n] += temp;
    }
    fin.close();
    return s[n];
}

Node* prob2(Battle* battles, int n)
{
    Node* p = battles;
    while (p != nullptr)
    {
        p->battle;
        p = p->next;
    }
    return p;
}

struct Date{
    int day, month, year;
};
