#include<iostream>
#include<fstream>
#include<sstream>
#include<string>
#include<vector>
#include<cmath>
using namespace std;

struct Date {
int day, month, year;
string era; // AD or BC
};
struct General {
string name, nationality;
Date born, death;
vector<string> known_battles;
};
struct Node {
General general;
Node* left;
Node* right;
};
vector<General> prob1(string filename)
{
 ifstream fi(filename);
 string s;
 string t,z,g;
 getline(fi,s);
 vector<General> v;
 int d=0;
 while (getline(fi,s,))
 {   stringstream ss(s);
     getline(ss,v[i].name,',') ;
     getline(ss,v[i].nationality,',');

     getline(ss,t,',');
     stringstream b(t);
     getline(b,z,'-');
     v[i].born.day= stoi(z);
     getline(b,z,'-');
     v[i].born.month= stoi(z);
     getline(b,z,' ');
     getline(b,g,);
     if (g=="AD")
     v[i].born.year= stoi(z)
     else v[i].born.year= -stoi(z);

     getline(ss,t,',');
     stringstream b(t);
     getline(b,z,'-');
     v[i].death.day= stoi(z);
     getline(b,z,'-');
     v[i].death.month= stoi(z);
     getline(b,z,' ');
     getline(b,g,);
     if (g=="AD")
     v[i].death.year= stoi(z)
     else v[i].death.year= -stoi(z);
     d++;

 }
 return v;

}
Node* cr(General x)
{ Node*p;
 p->general=x;
 p->left=NULL;
 p->right=NULL;

}
void chen(Node * r, int x);
{

}

Node* prob2(vector<General> generals)
{ vector<General> v= prob1(filename);
  int d=v.size();
  int* a= new int [d];
  for (int i = 0; i < testVector.size(); ++i)
  {a[i]= abs(v[i].born.year -1)*365+ (v[i].born.month -1)*30 + v[i].born.day ;
   if (v[i].born.year<0) a[i]=-a[i];
  }


}

