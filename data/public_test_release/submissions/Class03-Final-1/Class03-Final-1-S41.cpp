#include <iostream>
#include <string>

using namespace std;

int main()
{
    string ten;
    string ho;
    cin >> ten >> ho;
    int sz_ten = ten.size();
    string ans = "";
    ans += ten[0];
    int idx_ten = 1, idx_ho = 0;
    while (idx_ten < sz_ten)
    {
        if (ten[idx_ten] < ho[idx_ho])
            ans += ten[idx_ten++];
        else break;
    }
    ans += ho[idx_ho];
    cout << ans << endl;
}
