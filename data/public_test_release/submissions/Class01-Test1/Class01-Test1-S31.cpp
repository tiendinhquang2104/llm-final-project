#include<iostream>
#include<fstream>
#include<sstream>
#include<string>
using namespace std;
struct Node{
    General general;
    Node* next;
};
struct Date{
    int day,month, year;
    string era;
};
struct General{
    string name, nation;
    Date born, death;
    int tatal_knowns_battles;
    string* battles;
};

int tachNam(const string& s){
    return stoi(s.substr(s.size() - 7, 4));
}
string* tachTran( string& s){
    string res;
    string* temp= 0;

    for(char c : s){
        if( c == '|'){
            res.push_back(*temp);
            temp* = next;
        }else{
            temp += c;
        }
    }
    if(!temp.empty)
    return res;
}
General* prob1( string filename, int& n);
General list;
ifstream fin();

if(!fin.is_open)
return list;

string line;
stringstream ss(line);
getline(fin,line);

while(getline(fin, line)){
    General g;

    getline(ss, g.born, ',');

    getline(ss, temp,',');
    g.death = tachNam(temp);
     getline(ss, temp,',');


}

