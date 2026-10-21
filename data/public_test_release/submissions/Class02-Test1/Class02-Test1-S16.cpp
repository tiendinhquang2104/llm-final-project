#include<iostream>
#include<fstream>
#include<sstream>
#include<string>

using namespace std;

struct Battle
{
	string name, location;
	string from_date, to_date;
	int total_famous_general;
	string* list_famous_generals;
};

struct Node
{
	Battle battle;
	Node* next;
};

struct Date
{
	int year;	
};


int countLine(string filename)
{
	ifstream fin(filename);
	
	int count = 0;
	
	string line;
	getline(fin,line);
	
	while(getline(fin,line))
	{
		if(!line.empty())
		{
			count++;
		}
	}
	
	fin.close();
	
	return count;
}

int countFamous(string line)
{
	int count = 0;
	
	for(int i = 0; i < line.length(); i++)
	{
		if(line[i] == ';')
		{
			count++;
		}
	}
	
	return count + 1;
}

string* list_famous(string line, int size)
{
	string* list = new string[size];
	
	int start = 0;
	int end = 0;
	
	for(int i = 0; i < size; i++)
	{
		end = line.find(';',start);
		
		if(end == -1 )
		{
			list[i] = line.substr(start);
		}
		else
		{
			list[i] = line.substr(start,end - start);
			start = end + 1;
		}
	}
	
	return list;
}

Battle splitData(string line)
{
	Battle temp;
	
	stringstream fin(line);
	
	string line1;
	
	getline(fin, line1,',');
	temp.name = line1;
	
	getline(fin, line1,',');
	temp.location = line1;
	
	getline(fin, line1,',');
	temp.from_date = line1;
	
	getline(fin, line1,',');
	temp.to_date = line1;
	
	getline(fin, line1,',');
	
	getline(fin, line1,',');
	
	getline(fin, line1);
	temp.total_famous_general = countFamous(line1);
	temp.list_famous_generals = list_famous(line1, temp.total_famous_general);
	
	return temp;
}

Battle* prob1(string filename, int& n)
{
	n = countLine(filename);
	
	Battle* ans = new Battle[n];
	
	ifstream fin(filename);
	
	if(!fin.is_open())
	{
		cout<<"Error"<<endl;
		return ans;
	}
	
	string line;
	getline(fin, line);
	
	int i = 0;
	
	while(getline(fin,line) && i < n)
	{
		ans[i] = splitData(line);
		i++;
	}
	
	fin.close();
	
	return ans;
}

Node* createNode(Battle data)
{
	Node* newNode = new Node;
	
	newNode -> battle = data;
	newNode -> next = nullptr;
	
	return newNode;
}

void addHead(Node* &head, Battle data)
{
	if(head == nullptr)
	{
		return;
	}
	
	Node* addNode = createNode(data);
	
	addNode -> next = head;
	head = addNode;
	
}


Node* prob2(Battle* battles, int n)
{
	Node* head = nullptr;
	
	for(int i = n - 1; i > 0; i--)
	{
		addHead(head, battles[i]);
	}
	
	return head;
}

 int splitDate(string line)
{
	int year = stoi(line.substr(6,4));
	
	return year;
}



int prob3(Node* head, string start_year, string end_year)
{
	int count = 0;
	
	int start = stoi(start_year);
	int end = stoi(end_year);
	
	Node* curr = head;
	
	while(curr != nullptr)
	{
		if( start <= splitDate(curr -> battle.from_date) && splitDate(curr -> battle.to_date) <= end )
		{
			count++;
		}
		curr = curr -> next;
	}
	
	return count;
}


void prob4(Node* &head, string general)
{
	Node* curr = head;
	
	int i = 0;
	
	while(curr -> next != nullptr)
	{
		bool b = false;
		for(int i = 0; i < curr->battle.total_famous_general; i++)
		{
			if(curr -> next -> battle.list_famous_generals[i] == general)
			{
				b = true;
			}
		}
		if(b)
		{
			Node* removeNode = curr -> next;
			curr -> next = removeNode -> next;
			delete removeNode;
		}
		else
		{
			curr = curr -> next;
		}
	}
}










