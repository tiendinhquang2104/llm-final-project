#include <iostream>
#include <fstream>
#include <string>
using namespace std;

struct Rec { int a, b; };

// P1: dem so dong truoc, sau do mo lai file de doc vao mang dong
Rec* prob1(string filename, int& n) {
    ifstream fin;
    fin.open(filename);
    int x, y;
    int soDong = 0;
    while (fin >> x >> y) {
        soDong = soDong + 1;
    }
    fin.close();
    n = soDong;
    Rec* arr = new Rec[soDong + 1];
    ifstream fin2;
    fin2.open(filename);
    for (int i = 0; i < soDong; i++) {
        fin2 >> arr[i].a >> arr[i].b;
    }
    fin2.close();
    return arr;
}

// P2
int prob2(Rec* arr, int n) {
    int tong = 0;
    for (int i = 0; i < n; i++) {
        int giaTri = (arr[i].a - arr[i].b);
        tong = tong + giaTri;
    }
    return tong;
}

// P3
int prob3(Rec* arr, int n) {
    int lonNhat = (arr[0].a - arr[0].b);
    for (int i = 1; i < n; i++) {
        int hienTai = (arr[i].a - arr[i].b);
        if (hienTai > lonNhat) {
            lonNhat = hienTai;
        }
    }
    return lonNhat;
}

// P4: in ket qua cau 2
void prob4(Rec* arr, int n) {
    int ketQua = prob2(arr, n);
    cout << ketQua;
}
