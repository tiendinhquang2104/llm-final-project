#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
#include <cstring>
#include <cmath>

using namespace std;

struct Date
{
    int day, month, year;
    string era; // AD or BC
};
struct General
{
    string name, nationality;
    Date born, death;
    int total_known_battles;
    string *known_battles;
};
// Problem 1
General *prob1(string filename, int &n);
General *prob1(string filename, int &n)
{
    ifstream fin(filename);
    if (!fin)
    {
        cout << "Cannot open file." << endl;
        return 0;
    }
    string header;
    getline(fin, header);
    fin.close();
    return 0;
}
struct Node
{
    General general;
    Node *next;
};
Node *prob2(General *generals, int n);
General prob3(Node *head);
void pro4(Node *&head, string nationality);
