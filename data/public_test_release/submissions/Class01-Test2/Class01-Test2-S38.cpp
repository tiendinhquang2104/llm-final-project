
#include <iostream>
#include <fstream>
#include <string>
#include <vector>
using namespace std;

struct Date{
int day, month, year;
string era; // AD or BC
};
struct General {
    string name, nationality;
    Date born, death;
    vector<string> known_battles;
};

Date parseDate(string s) {
    Date d;
    d.day = stoi(s.substr(0, 2));
    d.month = stoi(s.substr(3, 2));
    d.year = stoi(s.substr(6, 4));
    d.era = s.substr(11);
    return d;
};


string* splitBattles(string s, int& count) {
    count = 1;
    for (char c : s)
        if (c == '|') count++;

    string* arr = new string[count];

    int start = 0, idx = 0;
    for (int i = 0; i <= s.length(); i++) {
        if (i == s.length() || s[i] == '|') {
            arr[idx++] = s.substr(start, i - start);
            start = i + 1;
        }
    }
    return arr;
}

void splitCSV(string line, string col[], int& count) {
    count = 0;
    string temp = "";

    for (int i = 0; i < line.length(); i++) {
        if (line[i] == ',') {
            col[count++] = temp;
            temp = "";
        }
        else {
            temp += line[i];
        }
    }
    col[count++] = temp;
}


 vector<General> prob1(string filename)
 {

    ifstream fin(filename);
    if (!fin.is_open()) {
        cout << "Can't open file\n";
    }
    General arr[200];
    int n = 200;
    vector<General> testVector;
    for (int i = 0; i < n; ++i) {
        testVector.push_back(arr[i]); // Call the .push_back method of vector.
    }

    string line;
    getline(fin, line);

    while (getline(fin, line)) {
        string col[20];
        int c;

        splitCSV(line, col, c);

        if (c < 9) continue;

        arr[n].name = col[0];
        arr[n].nationality = col[1];
        arr[n].born = parseDate(col[2]);
        arr[n].death = parseDate(col[3]);

        n++;
    }

    fin.close();
    return;
}

int main() {
    vector<General> arr = prob1("C:/Users/ACER/Downloads/50-best-european-generals-cleaned-first-20.csv");

}