#include<iostream>
#include<vector>
#include<string>
#include<fstream>
#include<sstream>
#include<cmath>

using namespace std ;

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
vector<General> prob1(string filename){
    vector<General> g;
    ifstream fin(filename);
    if(fin.is_open()){
        string buffer;
        getline(fin,buffer,'\n');
        while(getline(fin,buffer,',')){
            General a;
            a.name=buffer;
            getline(fin,buffer,',');
            a.nationality=buffer;
            getline(fin,buffer,'-');
            a.born.day=stoi(buffer);
            getline(fin,buffer,'-');
            a.born.month=stoi(buffer);
            getline(fin,buffer,' ');
            a.born.year=stoi(buffer);
            getline(fin,buffer,',');
            a.born.era=buffer;
            getline(fin,buffer,'-');
            a.death.day=stoi(buffer);
            getline(fin,buffer,'-');
            a.death.month=stoi(buffer);
            getline(fin,buffer,' ');
            a.death.day=stoi(buffer);
            getline(fin,buffer,',');
            a.death.era=buffer;

            getline(fin,buffer,',');
            stringstream ss(buffer);
            string b1;
            while(getline(ss,b1,'|')){
                a.known_battles.push_back(b1);
            }
            getline(fin,buffer,'\n');
            g.push_back(a);
        }
    }
    else cout<<"errror";
    fin.close();
    return g;
}
Node* createNode( General g){
    Node*a=new Node;
    a->general=g;
    a->left=NULL;
    a->right=NULL;
    return a;
}
void insert(Node* &r, General g ){
    if(r==NULL) createNode(g);
    if(r->left==NULL&&r->right==NULL){
        if(g.born.year>r->general.born.year){
            r->right=createNode(g);
        } else if(g.born.year<r->general.born.year){
            r->left=createNode(g);
        } else{
            if(g.born.month>r->general.born.month){
                r->right=createNode(g);
            } else if(g.born.month<r->general.born.month){
                r->left=createNode(g);
            }  else{
                    if(g.born.month>r->general.born.month){
                        r->right=createNode(g);
                    } else if(g.born.month<r->general.born.month){
                        r->left=createNode(g);
                    } else{
                            if(r->general.death.day > g.death.day){
                                r->left=createNode(g);
                            } else if(g.death.day>r->general.death.day){
                                r->right=createNode(g);
                            }
                    }
            }
        }
    } else if(r->general.born.year<g.born.year){
        insert(r->left,g);
    } else if((r->general.born.year > g.born.year)){
        insert(r->right,g);
    } 
}
int prob3(Node* root, string born_year){
    int cnt=0;

    return cnt;
}
Node* prob2(vector<General> generals){
    Node* r=NULL;
    for(int i=0;i<generals.size();i++){
        insert(r,generals[i]);
    }
    return r;
}
int main(){
    string filename="50-best-european-generals-cleaned-first-20.csv";
    prob1(filename);
    return 0;
}
