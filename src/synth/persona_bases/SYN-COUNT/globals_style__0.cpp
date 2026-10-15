#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
using namespace std;

struct Rec
{
    int a, b;
};

int kq2, kq3;

Rec* prob1(string filename, int& n)
{
    ifstream f(filename);
    Rec* arr = new Rec[500];
    string line;
    n = 0;
    while (getline(f, line))
    {
        if (line.empty())
            continue;
        stringstream ss(line);
        ss >> arr[n].a >> arr[n].b;
        n++;
    }
    return arr;
}

int prob2(Rec* arr, int n)
{
    kq2 = n;
    return kq2;
}

int prob3(Rec* arr, int n)
{
    kq3 = arr[0].b;
    for (int i = 1; i < n; i++)
        if (arr[i].b < kq3)
            kq3 = arr[i].b;
    return kq3;
}

void prob4(Rec* arr, int n)
{
    int t;
    t = n;
    cout << t;
}
