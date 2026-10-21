#include <iostream>
#include <sstream>
#include <fstream>
#include <string>

using namespace std;

struct Battle {
    string name, location;
    string from_date, to_date;
    int total_famous_generals;
    string* list_famous_generals;
};

struct Node {
    Battle battle;
    Node* next;
};

int countRow(string filename) {
    int n = 0;
    ifstream fin;
    string line;
    fin.open(filename);
    getline(fin, line, '\n');
    while (getline(fin, line, '\n')) {
        n++;
    }
    return n;
}

Battle* prob1(string filename, int& n) {
    Battle* list = new Battle[n];
    ifstream fin;
    string line;
    fin.open(filename);
    getline(fin, line, '\n');
    for (int i = 0; i < n; i++) {
        string temp;
        getline(fin, temp, ',');
        cout << temp << endl;
        list[i].name = temp;
        getline(fin, temp, ',');
        cout << temp << endl;
        list[i].location = temp;
        getline(fin, temp, ',');
        cout << temp << endl;
        list[i].from_date = temp;
        getline(fin, temp, ',');
        cout << temp << endl;
        list[i].to_date = temp;
        getline(fin, temp, ',');
        getline(fin, temp, ',');
        int n_temp = 0;
        getline(fin, temp, '\n');
        stringstream generalTempList(temp);
        stringstream generalList(temp);
        string generalsTemp, generals;
        while (getline(generalTempList, generals, ';')) {
            n_temp++;
        }
        string* temp_list = new string[n_temp];
        int j = 0;
        while (getline(generalList, generals, ';')) {
            temp_list[j] = generals;
            j++;
        }
        list[i].total_famous_generals = n_temp;
        list[i].list_famous_generals = temp_list;
        cout << list[i].total_famous_generals << endl;
        for (int k = 0; k < n_temp; k++) {
            cout << list[i].list_famous_generals[k] << endl;
        }
    }
    return list;
}

bool checkNULL(Battle battle) {
    if (battle.name == "") {
        return 1;
    }
    else return 0;
}


Node* prob2(Battle* battles, int n) {
    Node* head = new Node;
    for (int i = 0; i < n; i++) {
        while (head->next!=NULL) {
            head = head->next;
        }
        head->battle = battles[i];
    }
    return head;
}

void printList(Node* pHead) {
    Node* temp = pHead;
    while (pHead->next != NULL){
        cout << pHead->battle.name << endl;
        pHead = pHead->next;
    }
}

int main()
{
    int n = countRow("50-european-battles-first-20.csv");
    Battle* listEuropean = prob1("50-european-battles-first-20.csv", n);
    Node* list = prob2(listEuropean, n);
    printList(list);
    return 0;

}

// Run program: Ctrl + F5 or Debug > Start Without Debugging menu
// Debug program: F5 or Debug > Start Debugging menu

// Tips for Getting Started: 
//   1. Use the Solution Explorer window to add/manage files
//   2. Use the Team Explorer window to connect to source control
//   3. Use the Output window to see build output and other messages
//   4. Use the Error List window to view errors
//   5. Go to Project > Add New Item to create new code files, or Project > Add Existing Item to add existing code files to the project
//   6. In the future, to open this project again, go to File > Open > Project and select the .sln file
