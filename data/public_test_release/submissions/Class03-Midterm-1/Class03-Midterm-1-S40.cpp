#include<iostream>
using namespace std;
long long luu[12];
int xuli(int n)
{
    int k=0;
    while(n!=0)
    {
        k++;
        n/=10;
    }
    return k;
}
long long tong(int a,int n)
{
   if(n==0) return 1;
   if(n==1) return a;
   long long ans = tong(a,n/2);
   ans*=ans;
   if(n%2==1) ans*=a;
   return ans;
}
int main()
{
    int n,a,dem;
    long long ans=0;
    cin>>n;
    dem=xuli(n);
    a=n;
    while(n!=0)
    {
        int k=n%10;
        if(luu[k]==0) luu[k]=tong(k,dem);
        ans+=luu[k];
        n/=10;
    }
    if(ans==a) cout<<"True";
    else cout<<"False";
    return 0;
}
