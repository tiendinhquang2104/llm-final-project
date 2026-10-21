#include <iostream> 
#include <sstream>
#include <string>
#include <fstream>

using namespace std;

//BattleName,Location,FromDate,ToDate,CountriesInvolved,Casualties,ListFamousGenerals

struct Date {
    int day;
    int month;
    int year;

    Date() : day(0), month(0), year(0) {}
};

struct Battle {
    string name, location;
    string from_date, to_date;
    int total_famous_generals;
    string* list_famous_generals;
    Date fromDate, toDate;

    Battle() : name(""), location(""), from_date(""), to_date(""), total_famous_generals(0), list_famous_generals(nullptr) {}
};

struct Node {
    Battle battle;
    Node* next;

    Node(): next(nullptr) {}
    ~Node() {
        delete(battle.list_famous_generals);
    }
    
};



Battle insert(const string& inStr) {
    stringstream ss(inStr);
    string inName, inLoc, inFromDate, inToDate, listGen;
    getline(ss, inName, ',');
    getline(ss, inLoc, ',');
    getline(ss, inFromDate, ',');
    getline(ss, inToDate, ',');
    getline(ss, listGen, ',');

    Battle Bat;
    Bat.name = inName;
    Bat.location = inLoc;
    Bat.from_date = inFromDate;
    Bat.to_date = inToDate;
    Bat.list_famous_generals = new string(listGen);
    return Bat;    
}

Battle* prob1(string filename, int& n) {
    fstream fs;
    string line;
    fs.open(filename);
    if(!fs.is_open()) {
        cout << "cant";
        return NULL;
    }
    Battle* listBat = new Battle[n];
    fs.open("50-european-battles-first-20.csv");
    fs >> line;
    for(int i = 0; i < n; ++i) {
        fs >> line;
        listBat[i] = insert(line);
    }
    cerr << "a";
    fs.close();
    return listBat;
}

Node* prob2(Battle* battles, int n) {
    Node* head;
    for(int i = 0; i < n; i++) {
        Node* newBat = new Node();
        if(head == nullptr) {
            head = newBat;
            head -> battle = battles[i];
        }
        else {
            Node* cur = head;
            while(cur -> next != nullptr) {
                cur = cur -> next;
            }
            cur -> next = newBat;
            cur = cur -> next;
            cur -> battle = battles[i];
        }
    }
    cerr << "b";
    return head;
}

void print(Node* head) {
    if(head == nullptr) return;
    Node* cur = head;
    while(cur != nullptr) {
        cout << cur -> battle.name << cur -> battle.location << cur -> battle.from_date << cur -> battle.to_date << cur -> battle.list_famous_generals << '\n';
        cur = cur -> next;
    }
    cerr << "c";
}


int main() {
    fstream fs;
    string FN = "50-european-battles-first-20.csv";
    fs.open(FN);
    if(!fs.is_open()) {
        cerr << "cant open file\n";
        return 0;
    }
    string line;
    fs >> line;
    int cnt = 0;
    while(!EOF) {
        fs >> line;
        cnt++;
    }
    fs.close();

    Battle* BattlesList = prob1(FN, cnt);
    for(int i = 0; i < cnt ;i++) {
        cout << BattlesList[i].name << '\n';
    }
    // Node* ListBat = prob2(BattlesList, cnt);
    // print(ListBat);
    return 0;
}

