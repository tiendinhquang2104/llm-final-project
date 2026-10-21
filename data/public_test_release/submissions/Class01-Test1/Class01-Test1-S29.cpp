#include <iostream>
#include <string>
#include <cmath>

using namespace std;

struct Date{
	int day, month, year;
	string era;
};

struct General{
 	string name, nationality;
 	Date born, death;
 	int total_known_battles;
 	string* known_battles;
 };
 
General* prob1(string filename, int& n);
 
struct Node{
 	General general;
 	Node* next;
 };
 
Node* prob2(General* generals, int n);
 
General prob3(Node* head);
 
void prob4(Node*& head, string nationality);
 
int main(){
 	return 0;
 }
