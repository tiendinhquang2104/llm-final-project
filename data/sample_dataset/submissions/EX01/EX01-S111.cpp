#include <iostream>
#include<fstream>
#include<string>
#include<sstream>
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

General* prob1(string filename, int& n)
{
    fstream fi(filename);
    string s,l;
    getline(fi,s);
    n=0;
    while (getline(fi,s)&& (!s.empty()))
        n++;
    fi.close();
    General* p;
    p= new General [n];
    fstream fin(filename);
    getline(fin,s);
    int d=0;
    while ( getline(fin,s)&& (!s.empty()))
          { d++;
            getline(fin,p[d].name,',');
            getline(fin,p[d]. nationality,',');
            getline(fin,l,',');
            stringstream ss (l);
            string ngay, cn;
            ss >> ngay >>cn;
            stringstream sa(ngay);
            getline(sa,s,'-');
            p[d].born.day= stoi(s);
            getline(sa,s,'-');
            p[d].born.month=stoi(s);
            getline(sa,s,);
            p[d].born.year=stoi(s);
            if  (cn=='BC')
              p[d].born.year= -p[d].born.year;

            getline(s,l,',');
            stringstream ss (l);
            string ngay, cn;
            ss >> ngay>>cn;
            stringstream sb(ngay);
            getline(sb,p[d].death.day,'-');
            getline(sb,p[d].death.month,'-');
            getline(sb,p[d].death.year,);
            if  (cn=='BC')
              p[d].death.year= -p[d].death.year;

            p[d].total_known_battles=0;
            getline(s,l,',');
            p[d].known_battles=0;
            stringstram ss(l);
            string k;
            while( getline(l,k,'|')&& !k.empty())
                p[d]total_known_battles++;

          }
        fin.close();
        return p;

}

















