#include<iostream>
using namespace std;
int a[10009],luu[10009],tam[10000008],dem=0;
bool check(int n)
{
    for(int i=1;i<=dem;i++) if(luu[i]==n) return 0;
    if(n>=0 && n<=10000000) tam[n]=1;
    return 1;
}
int main()
{
    int n;
    cin>>n;
    for(int i=1;i<=n;i++) cin>>a[i];
    luu[++dem]=a[1];
    if(a[1]>=0 && a[1]<=10000000) tam[a[1]]=1;
    for(int i=2;i<=n;i++)
        if(a[i]>=0 && a[i]<=10000000)
        {
            if(tam[a[i]]==0)
            {
                tam[a[i]]=1;
                luu[++dem]=a[i];
            }
        }
        else if(check(a[i])) luu[++dem]=a[i];
    cout<<dem<<'\n';
    for(int i=1;i<=dem;i++) cout<<luu[i]<<' ';
    return 0;
}
