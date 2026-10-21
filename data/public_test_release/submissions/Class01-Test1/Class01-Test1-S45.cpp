#include <fstream>
#include <iostream>
#include <string>

using namespace std;

struct Date {
int day, month, year;
string era; // AD or BC
};
struct General {
string name, nationality;
Date born, death;
int total_known_battles;
string* known_battles;
};

struct Node {
General general;
Node* next;
};

General* prob1(string filename, int& n)
{
     
};

Node* prob2(General* generals, int n)
{

};

General prob3(Node* head)
{
    
};

void prob4(Node*& head, string nationality)
{

};

int main()
{

}
