#include<iostream>
#include<sstream>
#include<fstream>
#include<string>
#include<vector>
using namespace std;

struct Date {
	int day, month, year;
	string era; // AD or BC
};
struct General{
	string name, nationality;
	Date born, death;
	vector<string> known_battles;
};

struct Node {
	General general;
	Node* left;
	Node* right;
};

Date getdate(string s){
	Date d;
	char dash;
	stringstream ss(s);
	ss >> d.day >> dash >> d.month >> dash >> d.year >> d.era;
	return d;
}

vector<General> prob1(string filename){
	ifstream file(filename);
	vector<General> p;
	if(!file.is_open()) return p;
	string line;
	int n = 0;
	getline(file, line);
	while(getline(file, line)) if(!line.empty()) n++;
	file.clear(); file.seekg(0);
	int idx = 0;
	while(getline(file, line) && idx < n){
		stringstream ss(line);
		getline(ss, p[idx].name, ',');
		getline(ss, p[idx].nationality, ',');
		string date1, date2;
		getline(ss, date1, ',');
		getline(ss, date2, ',');
		p[idx].born = getdate(date1);
		p[idx].death = getdate(date2);
		string battles;
		getline(ss, battles, ',');
		int cnt = 1;
		for(char c : battles) if(c == '|') cnt++;
		for(int i = 0; i < cnt; i++){
			stringstream tmp(battles);
			getline(tmp, p[idx].known_battles[i] , '|');
		}
		string dash;
		for(int i = 0; i < 4; i++){
			getline(ss, dash, ',');
		}
		idx++;
	} 
	return p;
}


int prob3(Node* root, string born_year){
	stringstream ss(born_year);
	int y; char dash;
	int n = 0;
	string Era;
	ss >> y >> dash >> Era;
	if(root){
		if(root->general.born.year == y && root->general.born.era == Era){
			return n++ + prob3(root->left, born_year) + prob3(root->right, born_year);
		}else{
			if(root->general.born.era == Era && root->general.born.year > y){
				return n++ + prob3(root->left, born_year);
			}else if((root->general.born.era == Era && root->general.born.year < y))
				return n++ + prob3(root->right, born_year);
			else if(root->general.born.era != Era && Era == "BC"){
				return n++ + prob3(root->left, born_year); 
			}else{
				return n++ + prob3(root->right, born_year);
			}
		}
	}
	return n;
}

void prob4(Node*& root, string battle){
	
}

int main(){
	return 0;
}

