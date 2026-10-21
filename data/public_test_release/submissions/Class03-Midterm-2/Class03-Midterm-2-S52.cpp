#include <iostream>

using namespace std;

const int N = 10005;
typedef long long arr[N];
int n;
arr a, tmp_a, b, id, cnt_id;
bool not_first_time[N];
void Sort(arr& a,int l,int r)
{
    if(l == r){return ;}
    int mid = (l + r) / 2;
    Sort(a, l, mid);
    Sort(a, mid + 1, r);
    int i = l, j = mid + 1;
    int cnt = 0;
    while((i <= mid) || (j <= r))
    {
        cnt++;
        if(i > mid){b[cnt] = a[j]; j++;}
        else if(j > r){b[cnt] = a[i]; i++;}
        else if(a[i] < a[j]){b[cnt] = a[i];i++;}
        else {b[cnt] = a[j];j++;}
    }
    for(int i = 1; i <= cnt; i++)
    {
        a[l + i - 1] = b[i];
    }
}
int Find_k(arr a, int l, int r,int k)
{
    int pos = -1;
    while(l <= r)
    {
        int mid = (l + r) / 2;
        if(a[mid] < k){l = mid + 1;}
        else if(a[mid] > k){r = mid - 1;}
        else {pos = mid; break;}
    }
    return pos;
}
bool not_use[N];
int main()
{
    cin >> n;
    for(int i = 1; i <= n; i++)
    {
        cin >> a[i];
        tmp_a[i] = a[i];
    }
    int cnt = 0;
    for(int i = 1; i <= n; i++)
    {
        if(not_use[i]){continue;}
        cnt++;
        b[cnt] = a[i];
        for(int j = i + 1; j <= n; j++)
        {
            if(a[i] == a[j]){not_use[j] = 1;}
        }
    }
    cout << cnt << '\n';
    for(int i = 1; i <= cnt; i++)
    {
        cout << b[i] << ' ';
    }
//    Sort(tmp_a,1,n);
//    int Id = 1;
//    id[1] = 1;
//    for(int i = 2; i <= n; i++)
//    {
//        if(tmp_a[i] != tmp_a[i-1])
//        {
//            Id++;
//        }
//        id[i] = Id;
//        cnt_id[Id]++;
//    }
//    int cnt = 0;
//    for(int i = 1; i <= n; i++)
//    {
//        int pos_k = Find_k(tmp_a, 1, n, a[i]);
//        int Id = id[pos_k];
//        if(!not_first_time[Id])
//        {
//            cnt++;
//            b[cnt] = a[i];
//            not_first_time[Id] = 1;
//        }
//    }
//    cout << cnt << '\n';
//    for(int i = 1;i <= cnt; i++)
//    {
//        cout << b[i] << ' ';
//    }
    return 0;
}
