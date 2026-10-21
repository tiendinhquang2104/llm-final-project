#include <iostream>
#include <string>

using namespace std;



int main()
{
    string s;
    getline(cin,s);

    int n = s.length();
    int idxName;

    for (int i = 0; i < n; i++){
        if (s[i] == ' '){
            idxName = i+1;
            break;
        }

    }

    for (int i = 1; i < idxName-1; i++){
        if (s[i] > s[idxName]){
            cout << s[idxName];
            break;
        }
        if (s[i] == s[idxName]){
            if (s[i+1] > s[idxName+1]){
                cout << s[idxName];
                break;
            }
            else if (s[i+1] < s[idxName+1]){
                cout << s[i];
                if (s[i+1] == ' '){
                    cout << s[idxName];
                    break;
                }
            }
        }
        else{
            cout << s[i];
            if (s[i+1] == ' '){
                cout << s[idxName];
                break;
            }
        }
    }

    return 0;
}
