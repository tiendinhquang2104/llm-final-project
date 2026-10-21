#include <iostream>
#include <fstream>
#include <string>
#include <vector>

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

void openFile(){
    ifstream myFile("50-best-european-generals-cleaned-first-20.txt");
}

//problem 1
vector<General> prob1(string filename);

//problem 2
Node* prob2(vector<General> generals);

//problem 3
int prob3(Node* root, string born_year);

//problem 4
void prob4(Node*& root, string battle);

int main()
{

}