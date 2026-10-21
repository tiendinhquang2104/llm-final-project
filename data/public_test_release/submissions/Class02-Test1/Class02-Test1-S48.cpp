#include<iostream>
#include<fstream>
#include<string>
using namespace std;
struct Battle{
    string name,location;
    string from_date,to_date;
    int total_famous_generals;
    string list_famous_generals;

};
struct Node{
    Battle battle;
    Node*next;
};
struct sos{
    string total_famous_generals; // struct phụ 
};
Node*taonode(Battle a){
    Node*p=new Node;
    p->battle=a;
    p->next=NULL;
    return p;
}
int countline(string filename){
    ifstream filea(filename);
    string rac;
    int dem=0;
    getline(filea,rac);
    while(getline(filea,rac)){
        dem++;
    }
    filea.close();
    return dem;

}
int *demtuong(string filename,int n){
    int *m=new int[n];
    ifstream fileB(filename);
    string rac1;
    getline(fileB,rac1);
    for(int i=0;i<n;i++){
        int dem1=0;
        sos rac2;
        Battle temp;
        getline(fileB,rac1,',');
        getline(fileB,rac1,',');
        getline(fileB,rac1,',');
        getline(fileB,rac1,',');
        getline(fileB,rac1,',');
        getline(fileB,rac1,',');
        getline(fileB,rac2.total_famous_generals);
        for(char x:rac2.total_famous_generals){
            if(x==';') dem1++;
        }
        m[i]=dem1+1;
    }
    return m;
}
Battle *prob1(string filename,int &n){
    Battle *mang=new Battle[n];
    int *mang2=demtuong(filename,n);
    ifstream fileA(filename);
    string trash;
    getline(fileA,trash);
    for(int i=0;i<n;i++){
        Battle tmp;
        getline(fileA,tmp.name,',');
        getline(fileA,tmp.location,',');
        getline(fileA,tmp.from_date,',');
        getline(fileA,tmp.to_date,',');
        getline(fileA,trash,',');
        getline(fileA,trash,',');
        getline(fileA,tmp.list_famous_generals);
        mang[i]=tmp;
    }
    for(int i=0;i<n;i++){
        mang[i].total_famous_generals=mang2[i];
    }
    return mang;
}
Node*addtai(Node*head,Battle a){
    Node*newdata=taonode(a);
    if(head==NULL){
        head=newdata;
        return head;
    }
    Node*cur=head;
    while(cur->next != NULL){
        cur=cur->next;
    }
    cur->next=newdata;
    return head;

}
Node*prob2(Battle *battles,int n){
    Node*head=NULL;
    for(int i=0;i<n;i++){
        head=addtai(head,battles[i]);
    }
}
void printmang(Battle *m,int n){
    for(int i=0;i<n;i++){
        cout<<m[i].name<<" "<<m[i].from_date<<" "<<m[i].to_date<<" "<<" "<<m[i].total_famous_generals
        <<" "<<m[i].list_famous_generals<<endl;
    }
}
int main(){
    int n=countline("50-european-battles-first-20.txt");
    cout<<n;
    cout<<endl;
    Battle *result=prob1("50-european-battles-first-20.txt",n);
    printmang(result,n);
    
}