#include <iostream>

using namespace std;

typedef long long ll;
const int N = 1e5 + 7;
const ll Chck = 1e9 + 7;

int n;
bool cnt[Chck];
ll arr_1[N], arr_2[N];

void input()
{
    cin >> n;
    for (int i = 0; i < n; ++i)
    {
        cin >> arr_1[i];
        cnt[arr_1[i]] = 1;
    }
}
void process()
{
   int tmp = 0;
   for (int i = 0; i < n; ++i)
   {
       if (cnt[arr_1[i]])
       {
           arr_2[tmp] = arr_1[i];
           ++tmp;
           cnt[arr_1[i]] = 0;
       }
   }
   for (int i = 0; i < tmp; ++i)
        cout << arr_2[i] << " ";
}

int main()
{
    input();
    process();
}
