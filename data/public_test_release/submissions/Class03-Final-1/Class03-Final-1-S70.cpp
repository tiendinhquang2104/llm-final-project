#include <iostream>
#include <string>
using namespace std;

int main(){
    string ten;
    cin >> ten;
    string ho;
    cin >> ho;
    string goptong = "";
    string nho = "zz";
    for(int i = 0;i < ten.size();i++){
        goptong = goptong + ten[i];
        string gop = goptong;
        for(int j = 0;j < ho.size();j++){
            gop = gop + ho[j];
            if(gop < nho){
                nho = gop;
            }
        }
    }
    cout << nho;

    return 0;
}
