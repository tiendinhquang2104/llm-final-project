#include<iostream>
#include<sstream>
#include<fstream>
#include<string>
using namespace std;
struct Battle {
	string name, location;
	string from_date, to_date;
	int total_famous_generals;
	string* list_famous_generals;
};
struct country{
	string country;
};
void tach(string s){
	country c;
	int pos;
	while(pos=s.find(",")!=string::npos){
		s.erase(0,pos);
	}
}
void tach2(string s){
	Battle u;
	u.total_famous_generals=stoi(s.substr(0,3));
}
string* tach3(string s){
	Battle u;
	string n;
	string*o=&s;
	u.list_famous_generals=o;
	return o;
}
Battle* prob1(string filename,int &n){
	ifstream fin(filename);
	string line;
	getline(fin,line);
	while(true){
		Battle u;
		string tmp;
		if(getline(fin,u.name,',')) return nullptr;
		getline(fin,u.location,',');
		getline(fin,u.from_date,',');
		getline(fin,u.to_date,',');
		getline(fin,tmp,','); tach(tmp);
		getline(fin,tmp,',');tach(tmp);
		getline(fin,tmp,',');
		return u
	}
	
fs.close();
}
struct Node{
	Battle battle;
	Node* next;
};
return u
int main(){
	string filename=("50-european-battles-first-20.csv");
	int n=50;
	Battle* x;
	x=prob1(filename, n);
}
