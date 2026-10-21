#include <iostream>
#include <fstream>
#include <sstream>
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
 General* prob1(string filename, int& n){
fstream infile(filename);
if(!infile_isopen){
    n=0;
    return 0;
};
string line;
n=0;
getline(infile,line);
while(getline(infile,line)){if(!infile.empty());n++};

 General* d=new ds[n];
infile.clear();
infile.seekg(0);
getline(infile,line);
string Tval;
int i;
while(i<n && getline(infile,ds.name[i],',')){
getline(infile,ds.nationality[i],',');
getline(infile,ds.born.day[i],'-');ds.born.day[i]=stoi(Tval);
getline(infile,ds.born.month[i],'-');ds.born.month[i]=stoi(Tval);
getline(infile,ds.born.year[i],',');ds.born.year[i]=stoi(Tval);
getline(infile,ds.born.era[i],',');

getline(infile,Tval,'-');ds.death.day[i]=stoi(Tval);
getline(infile,Tval,'-');ds.death.month[i]=stoi(Tval);
getline(infile,Tval,',');ds.death.year[i]=stoi(Tval);
getline(infile,Tval,',');

getline(infile,Tval,',');ds.total_known_battles[i]=stoi(Tval);
getline(infile,ds.known_battles[i]);

i++;
};
file.close();
return ds;
 };
Node* prob2(General* generals, int n){
Node* generals;
Node* next;
while(generals->ds->next != nullptr){
generals->ds->next;
 };
 };
int main(){
    return 0;
}