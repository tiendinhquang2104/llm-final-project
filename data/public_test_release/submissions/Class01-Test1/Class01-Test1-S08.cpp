#include <iostream>
#include <string>
#include <fstream>
using namespace std;
struct Date {
    int day, month, year;
    string era; //AD or BC
};
struct General {
    string name, nationality;
    Date born, death;
    int total_known_battles;
    string* known_battles;
};
General* prob1(string fin, int& n){
    ifstream("war.csv");
    Date event;
    General human;
    getline(Date , n);
    getline(General , fin);
   for(int i=0; i<=n;i++){
        cout << [i] << " ";
   }
   return 0;
}
struct Node {
General general;
Node* next;
};
Node* prob2(General* generals, int n){
    int& a = new [1000];


}
General prob3(Node* head){

}
int sum(int a){
    int tong = 0;
    while(a>0){
        int le = a%10;
        tong +=a;
        a/=10;
    }
}
int main(){
    string a;
    int b;
    General* prob1(a, &b);
    sum(b);
    return 0;
}