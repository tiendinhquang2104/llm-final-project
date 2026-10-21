#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
using namespace std;
struct Date{
    int day, mounth, year;
    string era;
};

struct General{
    string name,nationality;
    Date born,death;
    int total_known_battles;
    string* known_battles;
};
struct Node{
    General general;
    Node* next;
};

int CountLine(string filename){
    int count = 0;
    fstream fin(filename);
    if(fin.fail()){
        cout << "Erorr opening file!" << endl;
        return 0;
    }

    string line;
    getline(fin,line);

    while(getline(fin,line)){
        ++count;
    }

    fin.close();
    return count;
}

Date parseDate(string strDate){
    Date d = {0, 0, 0, ""};
    if(strDate == "None" || strDate.empty()) return d;

    for(int i = 0; i < strDate.length(); ++i){
        if(strDate[i] == '-') strDate[i] = ' ';
    }
    
    stringstream ss(strDate);
    ss >> d.day >> d.mounth >> d.year >> d.era;
    return d;
}

General* prob1(string filename, int& n){
    General* myarr = new General [CountLine(filename)];

    ifstream fin(filename);
    if(fin.fail()){
        cout << "Erorr opening file!" << endl;
        return 0;
    }

    string line;
    getline(fin,line);
    
    int count = 0;
    while(getline(fin,line) && count < CountLine(filename)){
        string temptBorn, temptDeath,temptKnow_battles, tempt;
        stringstream ss(line);

        getline(ss, myarr[count].name, ',');
        getline(ss, myarr[count].nationality, ',');
        getline(ss, temptBorn, ',');
        getline(ss, temptDeath, ',');
        getline(ss, temptKnow_battles, ',');
        getline(ss, tempt, ',');
        getline(ss, tempt, ',');
        getline(ss, tempt, ',');
        getline(ss, tempt, '\n');
        myarr[count].total_known_battles = tempt.empty() ? 0 : stoi(tempt);
        myarr[count].known_battles  = &temptKnow_battles;

        myarr[count].born = parseDate(temptBorn);
        myarr[count].death = parseDate(temptDeath);

        ++count;
        
    }
    n = CountLine(filename);
    fin.close();
    return myarr;
}

Node* prob2(General* generals, int n){
    Node* head = new Node;
    int i = 0;
    head -> general = generals[i];
    
    Node* pCur = head;
    ++i;
    while(i < n){
        Node* newNode = new Node;
        newNode -> general = generals[i];
        pCur-> next = newNode;
        pCur = pCur -> next;
        ++i;
    }

    return head;
}

int Age(Node* head){
    int age = 0;
    if(head -> general.born.era == "BC" && head-> general.death.era == "AC"){
        age = head -> general.born.year + head -> general.death.year;
    }
    else if (head -> general.born.era == "AC" && head-> general.death.era == "AC"){
        age = head -> general.death.year - head -> general.born.year;
    }
    else if(head -> general.born.era == "BC" && head-> general.death.era == "BC"){
        age = head -> general.born.year - head -> general.death.year;
    }
    return age;
}
General prob3(Node* head){
    General a = head -> general;

    Node* pCur = head -> next;
    Node* pPre = head;
    
    while(pCur != NULL){
        if (Age(pCur) > Age(pPre)) a = pCur -> general;
        pPre = pCur;
        pCur = pCur -> next;
    }
    return a;
}

void prob4(Node*& head, string nationality){
    Node* pCur = head;
    if (head -> general.nationality == nationality){
        head = head -> next;
        delete pCur;
        pCur = head;
    }

    Node* pDelete = pCur;
    pCur = pCur -> next;
    while(pCur != NULL){
        if (pCur -> general.nationality == nationality){
            pCur = pCur -> next;
            delete pDelete;
        }
        else{
            pDelete = pCur;
            pCur = pCur -> next;
        }
    }
}



