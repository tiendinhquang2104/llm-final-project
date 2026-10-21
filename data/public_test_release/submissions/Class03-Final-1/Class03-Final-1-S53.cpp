#include<iostream>
#include<string>



using namespace std;




int main() {

    string s1, s2;
    cin >> s1 >> s2;
    int num1 = s1.size();
    s1 = " " + s1;
    char pivot = s2[0];
    int tmp = pivot - 'a';
    string res = "";
    res += s1[1];
    for (int i = 2; i <= num1; ++i) {
        int cur1 = s1[i] - 'a';
        if (cur1 >= tmp) break;
        res = res + s1[i];
    }
    res += pivot;
    cout << res;



    return 0;
}






