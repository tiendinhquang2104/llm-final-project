#include<bits/stdc++.h>
struct Battle{
    string name, location;
    string from_date, to_date;
    int total_famous_general;
    string* list_famous_general;
};

struct Node {
Battle battle;
Node* next;
}

Battle* prob1(string filename, int &n){
    cin>> n;
    Battle* arr=new Battle[n];
    ifstream file(filename);
    int i=0; string line;
    while(getline(fin, line)){
        stringstream ss;
        string tmp;
        getline(ss, tmp,",");
        arr[i].name=stof(tmp);
        getline(ss, tmp,",");
        arr[i].location=stof(tmp);
        getline(ss, tmp,",");
        arr[i].from_date=stof(tmp);
        getline(ss, tmp,",");
        arr[i].to_date=stof(tmp);
        getline(ss, tmp,",");
        arr[i].total_famous_general=int(atof(tmp));
        getline(ss, tmp,",");
        arr[i].list_famous_general=tmp;
        i++;
    }
    file.close();
    return arr;
}
