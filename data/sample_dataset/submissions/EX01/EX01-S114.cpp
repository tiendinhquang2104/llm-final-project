#include <iostream>
#include <string>
#include <fstream>
#include <cstring>

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

int CountLine(string filename)
{
    int count = 0;
    fstream file;
    string line = "";
    string ignore = "";
    file.open(filename);
    getline(file, ignore, '\n');
    while(getline(file, line, '\n'))
    {
        count++;
    }
    file.close();
    return count;
}

General* prob1(string filename, int& n)
{
    n = CountLine(filename);
    General* ptr = new General[n];
    fstream file;
    string line = "";
    string ignore = "";
    file.open(filename);
    getline(file, ignore, '\n');
    for(int i = 0; i < n; i++)
    {
        getline(file, ptr[i].name, ',');
        getline(file, ptr[i].nationality, ',');
        getline(file, line, '-');
        ptr[i].born.day = stoi(line);
        getline(file, line, '-');
        ptr[i].born.month = stoi(line);
        getline(file, line, ' ');
        ptr[i].born.year = stoi(line);
        getline(file, ptr[i].born.era, ',');
        getline(file, line, '-');
        ptr[i].death.day = stoi(line);
        getline(file, line, '-');
        ptr[i].death.month = stoi(line);
        getline(file, line, ' ');
        ptr[i].death.year = stoi(line);
        getline(file, ptr[i].death.era, ',');
        getline(file, line, ',');
        int total = 0;
        while(getline(file, line , '|'))
        {
            string* temp = new string;
            temp = &line;
            ptr[i].known_battles = temp;
            total++;
            if(getline(file, line , ',')) break;
        }
        total++;
        ptr[i].total_known_battles = total;
        
        getline(file,line, '\n');
        file.close();
    }
    return ptr;
}
