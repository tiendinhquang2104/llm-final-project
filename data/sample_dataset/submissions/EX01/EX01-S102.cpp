#include<iostream>
#include<string>
#include<cmath>
#include<fstream>

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



int countLines(string fileName){
    int n = 0;
    ifstream fin(fileName);

    if(!fin){
        cerr <<"cannot open file to read to count line";
        return -1;
    }
    
    string line;

    while(getline(fin, line)){
        ++n;
    }

    fin.close();

    return n;
}

void spilitFields(string line, string *fields){
    string field = "";
    int idx = 0;
    for(int i = 0; i < line.length(); ++i){
        if(line[i] == ','){
            fields[idx++] = field;
            field = "";
        }
        else{
            field += line[i];
        }
    }
    fields[idx] = field;
}

Date readDate(string field){
    // 31-12-1360 AD
    // dd - mm - yy - era
    // int day, month, year;
    // string era; // AD or BC
    string day[4];
    int idx = 0;
    Date d;
    for(int i = 0; i < field.length(); ++i){
        if(field[i] == '-' || field[i] == ' '){
            ++idx;
        }
        else{
            day[idx] += field[i];
        }
    }
    d.day = stoi(day[0]);
    d.month = stoi(day[1]);
    d.year = stoi(day[2]);
    d.era = day[3];
    
    return d;
}
int count_total_battle(string line){
    int cnt = 0;
    for(int i = 0; i < line.length(); ++i){
        if(line[i] == '|'){
            ++cnt;
        }
    }
    return cnt + 1;
}
string *readBattle(int &n, string line){
    n = count_total_battle(line);
    string * known_battle = new string [n];
    int idx = 0;
    for(int i = 0; i < line.length(); ++i){
        if(line[i] == '|'){
            idx++;
        }
        else{
            known_battle[idx] += line[i];
        }
    }
    return known_battle;
}
General readGeneral(string line){
    // string name, nationality;
    // Date born, death;
    // int total_known_battles;
    // string* known_battles;
    string fields[9];
    spilitFields(line, fields);

    int idx = 0;
    General g;
    g.name = fields[0];
    g.nationality = fields[1];
    g.born = readDate(fields[2]);
    g.death = readDate(fields[3]);
    //Siege of Acre|Battle of Arsuf|Battle of Jaffa
    g.total_known_battles = count_total_battle(fields[4]);
    g.known_battles = readBattle(g.total_known_battles, fields[4]);

    return g;
}
// Problem 1 (1) Write a function to read all records from the file filename into a dynamically allocated array of General.
// The order of generals in the array must match their order in the file.
// Note: If you fail to read the file, the remaining problems will not be graded.
// Prototype:
General* prob1(string filename, int& n){
    n = countLines(filename) - 1;

    ifstream fin(filename);

    if(!fin){
        cerr << "cannot open file read ";
        return nullptr;
    }

    General * g = new General[n];
    string line;
    getline(fin, line);
    int idx = 0;

    while(getline(fin, line)){
        g[idx++] = readGeneral(line);
    }

    fin.close();
    return g;
}
// For the following problems, use the structure below for a Node in a Singly Linked List:
struct Node {
    General general;
    Node* next;
};
// Problem 2 (4) Create a linked list from a given array of General. The order of generals in the list must match their order in
// the array.
// Prototype:
Node* addTail(Node*& pHead, General g){
    if(!pHead){
        return new Node{g, nullptr};
    }
    Node * newNode = new Node {g, nullptr};

    Node * pCurr = pHead;
    while(pCurr -> next){
        pCurr = pCurr -> next;
    }
    pCurr -> next = newNode;

    return pHead;
}
Node* prob2(General* generals, int n){
    Node * pHead = nullptr;
    for(int i = 0; i < n; ++i){
        addTail(pHead, generals[i]);
    }
    return pHead;
}
// Problem 3 (2) For this problem, a general’s age is calculated as death.year - born.year. However, note that some generals
// were born Before Christ (BC), so you must adjust the formula to handle this case.
// Find the oldest general in the list created in Problem 2. If there are multiple generals with the same highest
// age, return the first one encountered. You must operate in-place (i.e., without using extra lists, arrays, etc.).
// Prototype:
int countYear(General g){
    if(g.born.era == g.death.era){
        return abs(g.death.year - g.born.year);
    }
    else{
        return g.born.year + g.death.year;  
    }
}
General prob3(Node* head){
    if(!head){
        return {};
    }
    Node *pCurr = head;
    General g = {};
    int max_year = 0;
    while(pCurr){
        if(countYear(pCurr->general) > max_year){
            max_year = countYear(pCurr->general);
            g = pCurr ->general;
        }
        else{
            pCurr = pCurr -> next;
        }
    }
    return g;
}


// Problem 4 (3) Remove all generals with a given nationality from the list created in Problem 2. You must remove nodes
// in-place (i.e., without using extra lists, arrays, etc.).
// Prototype:
void prob4(Node*& head, string nationality){
    Node * pCurr = head;
    if(!head){
        return;
    }
    Node * pPrev = nullptr;
    while(pCurr ){
        if(pCurr -> general.nationality == nationality){
            Node *pTemp = pCurr;
            pPrev -> next = pCurr -> next;
            pCurr = pCurr ->next;
            delete pTemp;
        }
        else{
            pPrev = pCurr;
            pCurr = pCurr -> next;
        }
    }
}

int main(){
    cout << countLines("50-best-european-generals-cleaned-first-20.csv") << endl;
    Date d = readDate("06-17-1888 AD");
    cout << d.day << "/" << d.month << "/" << d.year << " in " << d.era;
    int n;

    General* gs =  prob1("50-best-european-generals-cleaned-first-20.csv", n);
}