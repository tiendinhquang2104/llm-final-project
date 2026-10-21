#include <iostream>
#include <fstream>
#include <cstring>

using namespace std;


int main(){
    string s, t = "", ho, ten;
    bool fre = 0;
    getline(cin, s);
    s = s + ' ';
    for (int i = 0; i < s.size(); i++){
        if (s[i] == ' '){
            if (fre == 0) ho = t;
            else ten = t;
            t = "";
            fre = 1;
            continue;
        }
        t = t + s[i];
    }
    t = "";
    char k = ten[0];
    if (ho[0] > k){
        t += ho[0];
        for (int i = 1; i < ho.size(); i++){
            if (ho[i] < k) t = t + ho[i];
            else break;
        }
        t += k;
        cout << t;
    }
    else{
        for (int i = 0; i < ho.size(); i++){
            if (s[i] < k) t += s[i];
            else break;
        }
        t += k;
        cout << t;
    }
    return 0;
}
