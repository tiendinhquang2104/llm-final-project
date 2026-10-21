#include <iostream>
#include <iomanip>
#include <string>
#include <sstream>
#include <fstream>
#include <cmath>
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
General* prob1(string filename, int& n){
    Date* bornn = new Date[21];
    int cnt1 = 0;
    Date* deathh = new Date[21];
    int cnt2 = 0;
    General* general = new General[21];
    n = 0;
    ifstream fin(filename);
    if(fin.is_open()){
        string line;
        getline(cin, line);
        while(getline(cin, line)){
            string A[9];
            int dem = 0;
            stringstream ss(line);
            string word;
            while(getline(ss, word, ',')){
                A[dem] = word;
                dem++;
            }
            string B1[15];
            string s1 = A[2];
            string s2 = A[3];
            stringstream ss1(s1);
            string cell1;
            int dem1 = 0;
            int dem2 = 0;
            while(getline(ss1, cell1, '-')){
                B1[dem1] = cell1;
                dem++;
            }
            string B2[15];
            stringstream ss2(s2);
            string cell2;
            while(getline(ss2, cell2, '-')){
                B2[dem2] = cell2;
                dem2++;
            }
            string C1[2];
            int dem3 = 0;
            string s3 = B1[2];
            stringstream ss3(s3);
            string tu3;
            while(getline(ss3, tu3)){
                C1[dem3++] = tu3;
            }
            string C2[2];
            int dem4 = 0;
            string s4 = B2[2];
            stringstream ss4(s4);
            string tu4;
            while(getline(ss3, tu4)){
                C2[dem4++] = tu4;
            }
            bornn[cnt1].day = stoi(B1[0]);
            bornn[cnt1].month = stoi(B1[1]);
            bornn[cnt1].year = stoi(C1[0]);
            bornn[cnt1].era = C1[1];
            
            // death
            deathh[cnt2].day = stoi(B2[0]);
            deathh[cnt2].month = stoi(B2[1]);
            deathh[cnt2].year = stoi(C2[0]);
            deathh[cnt2].era = C2[1];
            
            general[n].name = A[0];
            general[n].born.day = bornn[cnt1].day;
            general[n].born.month = bornn[cnt1].month;
            general[n].born.year = bornn[cnt1].year;
            general[n].born.era = bornn[cnt1].era;
            general[n].death.day = deathh[cnt1].day;
            general[n].death.month = deathh[cnt1].month;
            general[n].death.year = deathh[cnt1].year;
            general[n].death.era = deathh[cnt1].era;
            general[n].nationality = A[1];
            general[n].known_battles = &A[4];
            general[n].total_known_battles = stoi(A[8]);
            cnt1++;
            cnt2++;
            n++;
            
        }
        
        
    }
    fin.close();
    return general;
};
struct Node {
    General general;
    Node* next;
};
Node* prob2(General* generals, int n){
    Node * pHead = NULL;
    for(int i = 0; i < n; i++){
        Node* newNode = new Node();
        newNode->general.born.day = generals[i].born.day;
        newNode->general.born.month = generals[i].born.month;
        newNode->general.born.year = generals[i].born.year;
        newNode->general.born.era = generals[i].born.era;
        newNode->general.death.day = generals[i].death.day;
        newNode->general.death.month = generals[i].death.month;
        newNode->general.death.year = generals[i].death.year;
        newNode->general.born.era = generals[i].born.era;
        newNode->general.name = generals[i].name;
        newNode->general.nationality = generals[i].nationality;
        newNode->general.known_battles = generals[i].known_battles;
        newNode->general.total_known_battles = generals[i].total_known_battles;
        if(pHead == NULL){
            pHead = newNode;
        }
        else{
            Node* temp = pHead;
            while(temp->next != NULL){
                temp = temp->next;
            }
            temp->next = newNode;
        }
    }
    return pHead;
    
}

