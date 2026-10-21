#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

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
Node createNode(General gen){
    Node* r = new Node();
    r->general = gen;
    r->left = nullptr;
    r->right = nullptr;
}
vector<General> prob1(string filename){
    vector<General>  GenList;
     ifstream file(filename);
     if (!file.is_open()){
        return GenList;
     }
    string line;
     getline(file,line);
     string temp;
    while (getline(file , line))
    {   
        if(line.empty()){
            continue;
        }
          stringstream ss(line);
          General g;
          getline(ss, g.name,',' );
            getline(ss, g.nationality,',' );
          getline(ss,temp ,'-' );
            try{
                g.born.day = stoi(temp);
            }catch(...){
                   g.born.day = 0;
            }
            getline(ss,temp ,'-' );
            try{
                g.born.day = stoi(temp);
            }catch(...){
                   g.born.month = 0;
            }
            getline(ss,temp ,' ' );
            try{
                g.born.day = stoi(temp);
            }catch(...){
                   g.born.year = 0;
            }
            getline(ss, g.born.era,',' );

            getline(ss,temp ,'-' );
            try{
                g.death.day = stoi(temp);
            }catch(...){
                   g.death.day = 0;
            }
            getline(ss,temp ,'-' );
            try{
                g.death.day = stoi(temp);
            }catch(...){
                   g.death.month = 0;
            }
            getline(ss,temp ,' ' );
            try{
                g.death.day = stoi(temp);
            }catch(...){
                   g.death.year = 0;
            }
            getline(ss, g.death.era,',' );
              getline(ss,temp, ',');
              try
              {
                g.known_battles.push_back(temp);
              }catch(...){
                   g.death.era = "";
            }
            getline(ss,temp,',');
                
                g.known_battles.push_back(temp);

               GenList.push_back(g);
    }
   
    file.close();
    return GenList;
}
bool Older(general a, general b){
    if (a.born.year < b.born.year){
        if (a.born.era == 'AD' ==  b.born.era) return true;
        return false;
    }
    return false;
}
void insert(node* & r, general g){
    if (r == nullptr){
        createnode(g);
        return;
    }
    if (Older( r.general, g )) r->left = insert(r->left; g);
    else  if (Older(g ,r.general )) r->right = insert(r->right; g);
}
node* prob2(vector<general> generals){
    Node * root = new Node();
    for (int i = 0; i < generals.size(); i ++){
        insert(root, list[i]);
    }
 } 
void DisplayGen(General A){
    cout << A.name << A.nationality ;
}
// int prob3(Node* root, string born_year){
//     if (root == nullptr) return -1;
//     count  = if(root.born.year == born_year) 
//     return count + prob3(root->left,  born_year) +
// }
int main( ){
    string filename = "50-best-european-generals-cleaned-first-20.csv";
    vector<General> list;
    list = prob1( filename);
    for ( int i = 0; i < list.size(); i++){
        DisplayGen(list[i]);
    }

    return 0;
}