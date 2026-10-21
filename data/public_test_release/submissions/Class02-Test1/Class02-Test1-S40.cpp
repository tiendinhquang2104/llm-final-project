#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
using namespace std;
struct Battle
{
    string name, location;
    string from_date, to_date;
    int total_famous_generals;
    string* list_famous_generals;
};

struct Node
{
    Battle battle;
    Node* next;
};

struct Time
{
    int date;
    int month;
    int year;
};

Node* makeNode(Battle data)
{
    Node* newNode = new Node;
    newNode->battle = data;
    newNode->next = nullptr;
    return newNode;
}

void addTail(Node* &head, Battle data)
{
    Node* newNode = makeNode(data);
    if(head == nullptr)
    {
        head = newNode;
        return;
    }

    Node* temp = head;
    while (temp->next != nullptr)
    {
        temp = temp->next;
    }
    temp->next = newNode;
}

int countLine(string filename)
{
    int result = 0;
    string line;
    ifstream fs(filename);
    getline(fs, line, '\n');
    while (getline(fs, line, '\n'))
    {
        result++;
    }
    fs.close();
    return result;
}

int countSizeOfList(string line)
{
    int result = 0;
    stringstream ss(line);
    string data;
    while (getline(ss, data, ';'))
    {
        result++;
    }
    result++;
    return result;
}

string* toListOfGeneral(string line)
{
    int size = countSizeOfList(line);
    string* result = new string[size];
    int i = 0;
    stringstream ss(line);
    string data;
    while (getline(ss, data, ';'))
    {
        result[i] = data;
        i++;
    }
    return result;
}

Battle split(string line)
{
    Battle result;
    string data;
    stringstream ss(line);
    getline(ss, data, ','); result.name = data;
    getline(ss, data, ','); result.location = data;
    getline(ss, data, ','); result.from_date = data;
    getline(ss, data, ','); result.to_date = data;
    getline(ss, data, ','); result.total_famous_generals = countSizeOfList(data); result.list_famous_generals = toListOfGeneral(data);
    return result;
}

Time toTime1(string data)
{
    Time result;
    stringstream ss(data);
    string info;
    getline(ss, info, '-'); result.date = stoi(info);
    getline(ss, info, '-'); result.month = stoi(info);
    ss >> info; result.year = stoi(info);
    return result;
}

Time toTime(string data)
{
    Time result;
    stringstream ss(data);
    string info;
    getline(ss, info, '-'); result.date = stoi(info);
    getline(ss, info, '-'); result.month = stoi(info);
    ss >> info; result.year = stoi(info);
    return result;
}

bool checkTime(Time timeOfBattle, Time start, Time end)
{
    if(timeOfBattle.year < start.year || timeOfBattle.year > end.year) return false;
    if(timeOfBattle.month < start.month || timeOfBattle.month > end.month) return false;
    if(timeOfBattle.date < start.date || timeOfBattle.date > end.date) return false;
    return true;
}

Battle* prob1(string filename, int& n)
{
    n = countLine(filename);
    Battle* result = new Battle[n];
    int i = 0;
    ifstream fs(filename);
    string line;
    getline(fs, line, '\n');
    while (getline(fs, line, '\n'))
    {
        Battle info = split(line);
        result[i] = info;
        i++;
    }
    return result;
}

Node* prob2(Battle* battles, int n)
{
    Node* result = nullptr;
    for(int i = 0; i < n; i++) addTail(result, battles[i]);
    return result;
}

int prob3(Node* head, string start_year, string end_year)
{
    int result = 0;
    Time start = toTime(start_year);
    Time end = toTime(end_year);
    Node* temp = head;
    while (temp != nullptr)
    {
        Time timeOfBattle1 = toTime(temp->battle.from_date);
        Time timeOfBattle2 = toTime(temp->battle.to_date);
        if(checkTime(timeOfBattle1, start, end) && checkTime(timeOfBattle2, start, end)) result++;
        temp = temp->next;
    }
    return result;
}
int main()
{
    int n;
    Battle* listOfBattle = prob1("50-european-battles-first-20.csv", n);
    Node* head = prob2(listOfBattle, n);
    return 0;
}
