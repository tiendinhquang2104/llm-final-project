#include <iostream>
#include <fstream>
#include <string>
using namespace std;
struct Battle{
    string name,location;
    string from_date, to_date;
    int total_famous_generals;
    string* list_famous_general;

};
Battle* prob1(string file_name, int& n){
    fstream file_name;
    if (!file_name.is_open){
        cout<<"Can not be open the file"<<endl;
        return 0;
    }
}
