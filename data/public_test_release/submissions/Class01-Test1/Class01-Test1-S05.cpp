#include <iostream>
#include <string>
#include <fstream>
using namespace std;


struct Date {
    int day, month, year;
    string era; // AD or BC
};
struct General {
    string name, nationality;
    Date born, death;
    int total_known_battles;
    string* known_battles;}
struct Node {
    General general;
    Node* next;
}

General* prob1(string filename, int& n)
{
    ifstream fin(filename);
    string line;
    getline(fin, line);
    Date t;
    while (getline(fin, line))
    {
        int pos = 0;
        string field[10];
        int idx = 0;
        while (idx < 10)
        {
            int comma = line.find(",", pos);
            if (comma == string::npos) break;
        }
        field[idx] = line.substr(pos);

        t.day = stoi(field[0]);
        t.month = stoi(field[1]);
        t.year = stoi(field[2]);
        t.era = field[3];
        fin.close();
        return 0;}
}

int main()
{}
//struct thisinh{
//    string sbd;
//    string hoten;
//    float toan, van, ly, hoa, sinh;
//    float su, dia, gdcd;
//    float khtn, khxh, ngoaingu;
//    string ghichu;
//    string tinh;
//};
//float toFloat(string s)
//{
//    if (s == "") return -1;
//    return stof(s);
//}
//int main()
//{
//    ifstream fin("data.txt");
//    string line;
//    getline(fin, line);
//    thisinh t;
//    while (getline(fin, line))
//    {
//        int pos = 0;
//        string field[15];
//        int idx = 0;
//        while (idx < 14)
//        {
//            int comma = line.find(',', pos);
//            if (comma == string::npos) break;
//        }
//        field[idx] = line.substr(pos);
//
//        t.sbd = field[0];
//        t.hoten = field[1];
//        t.toan = toFloat(field[2]);
//
//
//        cout << t.sbd << ";" << t.hoten << "Toan";
//       for (int i = 0; i < 11; i++)
//       {
//           cout << ",";
//           if (t.thisinh[i] != -1)
//                cout << t.thisinh[i];
//       }
//        fin.close();
//        return 0;
//    }
//}
