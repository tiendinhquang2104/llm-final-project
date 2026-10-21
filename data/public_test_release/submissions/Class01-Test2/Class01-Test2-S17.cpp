#include <iostream>
#include <vector>
#include <fstream>
#include <vector>
#include <sstring>
using namespace std;

struct Date{
	int day, month, year;
	string era;
};

struct General{
	string name, nationality;
	Date born, death;
	vector<string> know_battles;
};

struct Node{
	General general;
	Node* left;
	Node* right;
};
vector<string> split(string s, char delimeter){
	vector<string> rs;
	string temp;
	stringstream ss(s);
	while(getline(ss, temp, delimeter)) rs.push_back(temp);
	return rs;
}
Date parseDate(const string& s){
	Date d;
	vector<string> parts = split(s, ' ');
	vector<string> nums = split(parts[0], '-');
	
	d.day = stoi(nums[1]);
	d.month = stoi(nums[2]);
	d.year = stoi(nums[3]);
	d.era = parts[1];
	return d;
}
vector<General> prob1(string filename){
	ifstream fin(filename);
	string line;
	
	if(!fin.is_open()) cout << "Invalid" << endl;
	
	getline(fin, line); // bo header;
	
	vector<General> res;
	int i = 0;
	while(getline(fin, line)){
		vector<string> temp = split(line, ',');
		
		General g;
		g.name = temp[0];
		g.nationality = temp[1];
		
		g.born = parseDate(temp[2]);
		g.death = parseDate(temp[3]);
		
		g.know_battles = split(temp[4],'|');
		
		res.push_back(g);
	}
	fin.close();
	return res;
}

//Problem 2
Node* createNode(General g){
	Node* newNode = new Node;
	newNode->general = g;
	newNode->left = NULL;
	newNode->right = NULL;
	return newNode;
}

Node* insert(Node* root, General g){
	if(!root) creatNode(g);
	if(g.born.year < root->general.born.year){
		root->left = insert(root->left, g);
	}
	else if(g.born.year > root->general.born.year){
		root->left = insert(root->right, g);
	}
	else if(g.born.year == root->general.born.year){
			if(g.death.year < root->general.death.year){
			root->left = insert(root->left, g);
			}
			if(g.death.year > root->general.death.year){
			root->right = insert(root->right, g);
			}
	}
	return root;
}

Node* prob2(vector<General> generals){
	Node* root = NULL;
	for(int i = 0; i < generals.size(); i++){
		root = insert(root, generals[i]);
	}
	return root;
}

// Problem 3


int prob3(Node* root, string born_year){
	vector<string> tmp = split(born_year, ' '); // temp[0] = year; temp[1] = era;
	int cnt = 0;
	if(!root) return;
	if(temp[0] < root->general.born.year){
		cnt = prob3(root->left, born_year);
	}
	else if(temp[0] > root->general.born. year){
		cnt = prob4(root->right, born_year);
	}
	else if(temp[0] == root->general.born.year){
		if(temp[1] == root->general.born.era){
			cnt++;
		}
	}
	return cnt;
}



// Problem 4


