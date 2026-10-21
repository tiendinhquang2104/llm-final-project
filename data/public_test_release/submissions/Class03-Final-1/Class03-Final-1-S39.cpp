#include<iostream>
#include<string>
#include<cstring>
using namespace std;
int main()
{
    string s,ans,tam,tam2,s2;
    getline(cin,s);
    int k=s.find(' ');
    s2=s.substr(k+1,s.size());
    ans=s[0];
    ans+=s[k+1];
    for(int i=1;i<=k;i++)
    {
        for(int j=k+2;j<=s.size();j++)
        {
            tam=s.substr(0,i);
            tam2=s2.substr(0,j-k-1);
            tam+=tam2;
            if(ans>tam) ans=tam;
        }
    }
    cout<<ans;
    return 0;
}
