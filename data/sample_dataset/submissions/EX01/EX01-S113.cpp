#include <iostream>
#include <fstream>
#include <cstring>
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

int countline(string filename) {
    fstream filein(filename);
    string line;
    getline(filein, line, '\n');
    int n = 0;
    while(getline(filein, line, '\n')) {
        ++n;
    }
    filein.close();
    return n;
}

int totalbattles(string filename, int i) {
    int n = countline(filename);

    General* G = new General[n];

    ifstream fin(filename);

    string line;

    int COUNT = 0;

    bool done = false;

    getline(fin, line, '\n');
    for (int j = 0; i < n; ++i) {
        getline(fin, G[i].name, ',');

        getline(fin, G[i].nationality, ',');

        getline(fin, line, '-');
        G[i].born.day = stof(line);

        getline(fin, line, '-');
        G[i].born.month = stof(line);

        getline(fin, line, ' ');
        G[i].born.year = stof(line);

        getline(fin, G[i].born.era, ',');

        if ( i != j) {
            getline(fin, line, '\n');
        }
        else if( i == j) {
            while(getline(fin, line, '|')) {
                ++COUNT;
                for (int i = 0; i >= 0; ++i) {
                    if (i > 50) break;
                    else if (line[i] == ',') {
                        done = true;
                        break;
                    }
                }
                if (done == true) break;
            }
        }

    }

    return COUNT;
}

string* battlesname(string filename, int i, int COUNT) {
    string* a = new string[COUNT];

    int m = countline(filename);

    General* G = new General[COUNT];

    ifstream fin(filename);

    string line;

    bool done = false;

    getline(fin, line, '\n');
    for (int j = 0; i < m; ++i) {
        getline(fin, G[i].name, ',');

        getline(fin, G[i].nationality, ',');

        getline(fin, line, '-');
        G[i].born.day = stof(line);

        getline(fin, line, '-');
        G[i].born.month = stof(line);

        getline(fin, line, ' ');
        G[i].born.year = stof(line);

        getline(fin, G[i].born.era, ',');

        if ( i != j) {
            getline(fin, line, '\n');
        }
        else if( i == j) {
            for(int i = 0; i < COUNT; ++i) {
                if (i < COUNT - 1) {
                    getline(fin, a[i], '|');
                }
                else if (i == COUNT - 1) {
                    getline(fin, a[i], ',');
                }
            }
        }

    }

    return a;
}

General* prob1(string filename, int& n) {
    n = countline(filename);
    General* G = new General[n];
    ifstream fin(filename);
    string line;
    getline(fin, line, '\n');
    for (int i = 0; i < n; ++i) {
        getline(fin, G[i].name, ',');

        getline(fin, G[i].nationality, ',');

        getline(fin, line, '-');
        G[i].born.day = stof(line);

        getline(fin, line, '-');
        G[i].born.month = stof(line);

        getline(fin, line, ' ');
        G[i].born.year = stof(line);

        getline(fin, G[i].born.era, ',');

        getline(fin, line, ',');
        G[i].total_known_battles = totalbattles(filename, i);
        G[i].known_battles = battlesname(filename, i, G[i].total_known_battles);
    }

    return G;
}

int main() {
}