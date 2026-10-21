#include <iostream>

typedef long long ll;

int main(){
    ll n, n_1, a[10], b[10], d = -1;
    std::cin >> n_1;
    n = n_1;
    ll count = 0;
    while(n > 0){
        a[count++] = n % 10;
        b[count-1] = 1;
        n /= 10;
    };
    ll sum = 0;
    while(sum < n_1 && d <= count){
        sum = 0;
        for(int i = 0; i < count; ++i){
            sum += b[i];
            b[i] *= a[i];
        };
        ++d;
    };
    if(sum == n_1 && d == count) std::cout << "True";
    else std::cout << "False";
    return 0;
};
