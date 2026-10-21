#include <iostream>

long long check (long long x) {
    long long temp, sum =0,k =0,dem =0, mu=1;
    temp = x;
    while (temp !=0){
        dem += 1;
        temp = temp/10;
    }
    while (temp !=0){
        k = temp%10;
        for (long long i = 0; i< dem;i++){
            mu *= k;
        }
        sum += mu;
        temp /= 10;
    }
    if (sum == x){
        std::cout<<"True";
    }
    else{
        std::cout<<"False";
    }
}

int main () {
    long long n;
    std::cin>>n;
    check (n);
}
