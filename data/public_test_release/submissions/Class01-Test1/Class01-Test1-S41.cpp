#include <iostream>
#include <fstream>
#include <string>
#include <cstring>
#include <cmath>
#include <sstream>
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
    ifstream fin(filename);
    Date d, b;
    if(!fin.is_open()){
        n = 0;
        return nullptr;
    }

    string line;
    int count = 0;
    getline(fin, line);

    while(getline(fin, line)){
        if(!line.empty()){
            count++;
        }
    }

    n = count;
    
    if(n == 0){
        fin.close();
        return nullptr;
    }

    fin.clear();
    fin.seekg(0);
    getline(fin, line);
    string temp, ListOfMedals, KnownPosition, LastPosition;




    General* generals = new General[n];
    for(int i = 0; i < n; i++){
        getline(fin, generals[i].name, ',');
        getline(fin, generals[i].nationality, ',');

        int dday, dmonth, dera;
        string tempyear, tempmonth, tempday;
        

        getline(fin, temp, ',');
        dday = temp.find('-');
        tempday = temp.substr(0, 2);
        b.day = stoi(tempday);
        
        dmonth = temp.rfind('-');
        tempmonth = temp.substr(dday + 1, 2);
        b.month = stoi(tempmonth);

        for(int i = 6; i < temp.length(); i++){
            if(temp[i] == ' '){
                break;
            }
            tempyear += temp[i];
        }
        b.year = stoi(tempyear);

        dera = temp.rfind(' ');
        b.era = temp.substr(dera + 1, 2);




        getline(fin, temp, ',');
        dday = temp.find('-');
        tempday = temp.substr(0, 2);
        d.day = stoi(tempday);
        
        dmonth = temp.rfind('-');
        tempmonth = temp.substr(dday + 1, 2);
        d.month = stoi(tempmonth);

        for(int i = 6; i < temp.length(); i++){
            if(temp[i] == ' '){
                break;
            }
            tempyear += temp[i];
        }
        d.year = stoi(tempyear);

        dera = temp.rfind(' ');
        d.era = temp.substr(dera + 1, 2);
        
        getline(fin, ListOfMedals, ',');
        getline(fin, KnownPosition, ',');
        getline(fin, LastPosition, ',');
        getline(fin, temp);
        generals[i].total_known_battles = stoi(temp);
    }
    fin.close();
    return generals;
}

// Node* prob2(General* generals, int n){
//     Node* head = nullptr;
//     Node* tail = nullptr;
//     for(int i = 0; i < n; i++){
//         Node* newNode = new Node;
//         newNode->data = generals[i];
//         newNode->next = nullptr;

//         if(head == nullptr){
//             head = newNode;
//             tail = newNode;
//         }else{
//             tail->next = newNode;
//             tail = newNode;
//         }
//     }
//     return head;
// }

// void prob4(Node*& head, string nationality){
//     if(head == nullptr) return;

//     Node* pCur = head;

//     if(head->data.nationality == nationality){
//         Node* temp = head;
//         head = head->next;
//         delete temp;
//     }

//     if(head == nullptr){
//         return;
//     }

//     while(pCur){
//         if(pCur->data.nationality == nationality){
//             Node* temp = pCur->next;
//             pCur->next = temp->next;
//             delete temp;
//         }
//         pCur = pCur->next;
//     }

// }



int main(){
    int n = 0;
    General* arr = prob1("file.csv", n);

    if(arr != nullptr){
        cout << 1;
    }else{
        cout << 2;
    }







    return 0;
}