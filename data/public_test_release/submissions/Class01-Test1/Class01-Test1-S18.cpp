#include<iostream>
#include<fstream>
#include<sstream>
#include<string>
struct Date {
	int day, month, year;
	std::string era; // AD or BC
};
struct General {
	std::string name, nationality;
	Date born, death;
	int total_known_battles;
	string* known_battles;
}
struct Node {
	General general;
	Node* next;
};
int countline(const char* filename)
{
	std::ifstream fin(filename);
	int count = 0;
	std::string line = "";
	if (fin.is_open())
	{
		std::getline(fin, line);
		while (std::getline(fin, line))
		{
			count++;
		}
		fin.close();
	}
	return count;
}
Date xuli(std::string&line)
{
	Date a;
	std::stringstream ss(line);
	std::string ngay = "";
	std::string thang = "";
	std::string nam = "";
	std::string theki = "";
	std::getline(ss, ngay, '-');
	std::getline(ss, thang, '-');
	std::getline(ss, nam, '');
	std::getline(ss, theki);
	a.day = stoi(ngay);
	a.month = stoi(thang);
	a.year = stoi(nam);
	a.era = theki;
	return a;
}
General* prob1(std::string filename, int& n)
{
	General* ptr = new General [n];
	std::ifstream fin(filename);
	if (fin.is_open())
	{
		std::string line = "";
		std::getline(fin, line);
		std::string ten = "";
		std::string quoctich = "";
		std::string birth = "";
		std::string died = "";
		std::string total = "";
		std::string knowbattles = "";
		std::string rong2 = "";
		std::string rong3 = "";
		for (int i = 0; i < n; i++)
		{
			std::getline(fin, line);
			std::stringstream ss(line);
			std::getline(ss, ten, ',');
			std::getline(ss, quoctich, ',');
			std::getline(ss, birth, ',');
			std::getline(ss, knowbattles, ',');
			std::getline(ss, rong2, ',');
			std::getline(ss, rong3, ',')
			std::getline(ss, died, ',');
			std::getline(ss, total, ',');
			ptr[i].name = ten;
			ptr[i].nationality = quoctich;
			ptr[i].born = xuli(birth);
			ptr[i].died = xuli(died);
			ptr[i].known_battles = knowbattles;
			ptr[i].total_known_battles = stoi(total);
		}
		fin.close();
	}
	return ptr;
}
Node* prob2(General* generals, int n)
{
	Node* pcurr = nullptr;
	Node* phead = nullptr;
	for (int i = 0; i < n; i++)
	{
		if (i == 0)
		{
			phead = generals[i];
			phead->next = pcurr;
		}
		else
		{
			pcurr = generals[i];
			pcurr->next = nullptr;
		}

	}
	return phead ;
}
int age(Node * curr)
{
	int agedied = curr->general.death.year;
	int agebirth = curr->general.born.year;
	int age = agedied - agebirth;
	return age;
}
General prob3(Node* head)
{
	Node* curr = head;
	int oldest = 0;
	int currage = 0;
	General cantim;
	while (curr->next != nullptr)
	{
		currage = age(curr);
		if (currage > oldest) oldest = currage;
	}
	while (curr->next != nullptr)
	{
		currage = age(curr);
		if (currage == oldest)
		{
			cantim = curr;
			break;
		}
	}
	return cantim;
}
