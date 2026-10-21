#include <iostream>
#include <sstream>
#include <fstream>
#include <string>
using namespace std;


struct Date {
int day, month, year;
string era; 
};

struct General {
string name, nationality;
Date born, death;
int total_known_battles;
string* known_battles;
};


int countline (string filename) {
    ifstream fin(filename);
    string line;

    int count = 0;
    while (getline (fin, line)) {
        count++;
    }
    fin.close();
    return count;
}

void slitline (General r, string file) {
    ifstream fin(file);
    string line;

    getline (fin, line);

}

General* prob1(string filename, int& n) {
    ifstream fin(filename);

    int count = countline(filename);
    General*a = new General[count];
    General*c;
    Date b, d;
    
    string line;
    // getline (fin, line);

    string btemp, dtemp, kbattle;
    string list, KPos, LPos, TotalWon;

    General arr1[100], arr2[100];  

    int i = 0;
    while(getline(fin, line)) {
        getline(fin, a[i].name, ',');
        getline(fin, a[i+1].nationality, ',');
        getline(fin, btemp, ',');
        getline(fin, dtemp, ',');
        getline(fin, kbattle, ',');
        getline(fin, list, ',');
        getline(fin, KPos, ',');
        getline(fin, LPos, ',');
        getline(fin, TotalWon, ',');
        

        string line1, days, months, years;
        stringstream s1(btemp);
        while (getline(s1,line1)) {
            getline(s1,days , '-');
            getline(s1,months , '-');
            getline(s1,years , '-');
        }
        // b.day = stoi(days);
        // b.month = stoi(months);
        // b.year = stoi(years);


        // stringstream s1(line1)
        // getline (s1, born)
        // s1 >> date;
        // arr1[i+2] = date;
        i++;
    }
    
    fin.close ();
    return c;
}
int main () {
    string ch = "generals.csv";
    int line = countline (ch);
    cout << prob1(ch, line);
}