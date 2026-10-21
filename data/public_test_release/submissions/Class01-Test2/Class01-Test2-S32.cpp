#include <iostream>
#include <vector>
#include <fstream>
#include <string>
using namespace std;
struct Date {
int day, month, year;
string era; // AD or BC
};

struct General {
string name, nationality;
Date born, death;
vector<string> known_battles;
}

struct Node {
General general;
Node* left;
Node* right;
}

int conv(string s){
try
{
    return stoi(s);
}
catch(...)
{}

}
vector<General> prob1(string filename){
ifstream(filename);
int num;
int line;
if(file_is.open != nullptr){
while(getline(filename,ds.name)){
    getline(filename,ds.nationality,",");

    getline(filename,ds.born.day,"-"); 
    num = conv(filename);
    getline(filename,ds.born.month,"-"); 
    num = conv(filename);
    getline(filename,ds.born.year," "); 
    num = conv(filename);
    getline(filename,ds.born.year,","); 


    getline(filename,ds.death.day,"-"); 
    num = conv(filename);
    getline(filename,ds.death.month,"-"); 
    num = conv(filename);
    getline(filename,ds.death.year," "); 
    num = conv(filename);
    getline(filename,ds.death.era,","); 

    getline(filename,ds.knowbattles,",");
    line++;

}
vector<int> ds;
for (int i = 0; i < line; ++i) {
ds.push_back(ds[i]); // Call the .push_back method of vector.
}
// From here, testVector behaves the same as an array.
// You can use .size() to know the vector’s size.
for (int i = 0; i < ds.size(); ++i) {
cout << ds[i] << " ";
}
file.close();
}
}
Node* prob2(vector<General> generals){

Node* proot = new General;
proot->left = proot->right = nullptr;


}

int main(){

    return 0;
}