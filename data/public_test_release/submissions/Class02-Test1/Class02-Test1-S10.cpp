#include <iostream>
#include <fstream>
#include <sstream>
#include <string>

using namespace std;

struct Battle {
	string name, location;
	string from_date, to_date;
	int total_famous_generals;
	string* list_famous_generals;
};

struct Node {
	Battle battle;
	Node* next;
};

int countline (string filename) {

	int cnt = 0;
	ifstream fin (filename);
	if(!fin.is_open()) return 0;
	string line;
	getline(fin, line);

	while (getline(fin, filename)) {
		if (!line.empty()){
			cnt++;
		}
	}
	fin.close();
	return cnt;
}

int dem (string s) {
	int cnt = 1;
	for (auto x : s) {
		if (x == ';') {
			cnt++;
		}
	}
	return cnt;
}

Battle splitdata (string line) {

	Battle b;
	stringstream ss (line);
	string tmp;

	getline (ss, tmp, ',');
	b.name = tmp;
	getline (ss, tmp, ',');
	b.location = tmp;
	getline (ss, tmp, ',');
	b.from_date = tmp;
	getline (ss, tmp, ',');
	b.to_date = tmp;
	getline (ss, tmp, ',');
	getline(ss, tmp, ',');
	b.total_famous_generals = dem(tmp);
	getline (ss, tmp, ',');
	*b.list_famous_generals = tmp;
	return b;
}

Battle* prob1 (string filename, int& n) {

	n = countline(filename);
	if(n==0) return nullptr;

	Battle* ans = new Battle[n];

	ifstream fin (filename);
	string line;
	getline(fin, line);
	int i = 0;
	while (getline(fin, line)&&i<n) {
		
		if (!line.empty()) {
			ans[i] = splitdata(line);
			i++;
		}
	
	}
	fin.close();
	return ans;
}

Node* prob2 (Battle* battles, int n){


}

int pro3 (Node* head, string star_year, string end_year) {
	int cnt = 0;
	Node*cur = head;
}

void pro4 (Node*& head, string general) {

}

