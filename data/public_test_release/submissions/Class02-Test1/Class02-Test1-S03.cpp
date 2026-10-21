#include <iostream>
#include <string>
#include <sstream>
#include <fstream>

using namespace std;

struct Battle {
    string name;
    string location;
    string from_date;
    string to_date;
    int total_famous_generals;
    string* list_famous_generals;
};

void gan(Battle a, Battle b){
    a.name = b.name;
    a.location = b.location;
    a.from_date = b.from_date;
    a.to_date = b.to_date;
    a.total_famous_generals = b.total_famous_generals;
    for(int i = 0; i <  a.total_famous_generals; i++){
        a.list_famous_generals[a.total_famous_generals] = b.list_famous_generals[a.total_famous_generals];
    }
}

 struct Node {
        Battle battle;
        Node* next;
    };

Battle* prob1(string filename, int& n){
    fstream file(filename);
    Battle* battle = nullptr;
    if(!file.is_open()){
        cout << "Khong the mo file";
        return battle;
    }
    else cout << "Mo duoc file";

   
    
    string line;
    getline(file, line);
    while(getline(file, line)){
        Battle war;
        stringstream ss(line);
        string temp, day, month, year;

        getline(ss, war.name, ',');
        getline(ss, war.location, ',');
        getline(ss, war.from_date, ',');
        getline(ss, war.to_date, ',');
        getline(ss, temp, ',');
        getline(ss, temp, ',');
        getline (ss, temp);

        int count = 0;
        stringstream general(temp);

        while(getline(general, war.list_famous_generals[count], ';')){
            count++;
        }
        war.total_famous_generals = count;
        gan(battle[n], war);
        n++;
    }
    cout << battle[0].name;
    file.close();
    return battle;
}

Node* prob2(Battle* battles, int n){
    Node* war = new Node;
    for(int i = 0; i < n; i++){
        gan(war->battle, battles[n]);
        war = war->next;
    }
    return war;
}

int main(){
    int n = 1;
    Battle *a = prob1("50-european-battles-first-20.csv", n);
    prob2(a, n);
    return 0;
}