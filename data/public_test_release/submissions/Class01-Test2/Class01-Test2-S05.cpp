#include <iostream>
#include <fstream>
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

#prob1
vector<General> prob1(string filename)
{
    ifstream in (filename);
    int n;
    in >> n;

    in.close();
}



#prob2
struct Node {
General general;
Node* left;
Node* right;
};
Node* prob2(vector<General> generals)


#prob3
int prob3(Node* root, string born_year)

#prob4
void prob4(Node*& root, string battle)


int main()
{

}
