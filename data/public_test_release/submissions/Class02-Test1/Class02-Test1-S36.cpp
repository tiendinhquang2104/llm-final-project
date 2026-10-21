#include <iostream>
#include <fstream>
#include <sstream>
#include <cstring>
#include <string>
#include <cmath>

struct Battle{
	std::string name, location;
	std::string from_date, to_date;
	int total_famous_generals;
	std::string* list_famous_generals;
}
struct Node {
	Battle battle;
	Node* next;
}

Battle* prob1(std::string filename, int& n) {
	Battle* ptr = new battle[n];
	std::ifstream ifs("50-european-battles-first-20.csv");
	if (ifs.is_open()) printf("File stream is created.\n");
	else printf("Error! File stream failed to be created.");
	
	ifs.seekg(69);
	std::string country, casualty;
	char c;
	int count = 0;
	
	for (unsigned int i=0; i < n && !(ifs.eof()); ++i) {
		ifs >> ((ptr + i) -> name);
		ifs >> ((ptr + i) -> location);
		std::getline(ifs, (ptr + i) -> from_date, '\n');
		std::getline(ifs, (ptr + i) -> to_date);
		std::getline(ifs, country);
		std::getline(ifs, casualty);
		while (ifs >> c && c != '\n') {
			if (c == ';') count += 1;