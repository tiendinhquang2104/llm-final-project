#include <iostream>

int main(){
    int n, n_b = 0, a[10000], b[10000];
    std::cin >> n;
    for(int i = 0; i < n; ++i){
        std::cin >> a[i];
        bool add = true;
        for(int j = n_b - 1; j >= 0; --j){
            if(a[i] == b[j]) add = false;
            break;
        };
        if(add) b[n_b++] = a[i];
    };
    std::cout << n_b << '\n';
    for(int i = 0; i < n_b; ++i)
        std::cout << b[i] << ' ';
    return 0;
};
