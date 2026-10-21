#include <iostream>
#include <sstream>
#include <fstream>
#include <string>
using namespace std;

struct Battle {
    string name;
    string location;
    string from_date, to_date;
    int total_famous_generals;
    string* list_famous_generals;
};
void splitandprint (const string&, char delim) {
    stringstream ss(s);
    string token;
    while (getline(ss, token, delim)) {
        cout <<token <<endl;
    }
}

Battle* prob1(string filename, int& n) {
if (n = nullptr) return 0;
ifstream fin("50-european-battles-first-20.csv");
if (!fin){ cout <<"Khong tim duoc file \n";}
return;
stringline;
getline(fin, file);
while (getline(fin,line)) {
stringstream ss (line);
}
}
int main() {
    return 0;
}