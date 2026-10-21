#include <iostream>
using namespace std;

int pow(int n, int c)
{
    int product = 1;
    for (int i = 1; i < c + 1; i++)
    {
        product *= n;
    }
    return product;
}

int numb(int n)
{
    int temp;
    int count;
    while (temp != 0)
    {
        temp = temp % 10;
        count++;
    }
    return count;
}
void inttoArray(int n, int array[])
{
    // int temp;
    // int count;
    // while (temp != 0)
    // {
    //     temp = temp % 10;
    //     count++;
    // }
    // return count;
    int i = 0;
    while (n != 0)
    {
        array[i] = n % 10;
        n = n / 10;
        i++;
    }
}

// bool isArm(int a)
// {
//     int so = a;
//     int temp = a;
//     int sum{};
//     int luythua = numb(a);
//     while (a != 0)
//     {
//         temp = a % 10;
//         a = a % 10;
//         sum += pow(temp, luythua);
//     }
//     if (so == sum)
//     {
//         return true;
//     }
//     return false;
// }

bool isArm(int a, int array[])
{
    inttoArray(a, array);
    int count = numb(a);
    int sum{};
    for (int i = 1; i < count; i++)
    {
        sum += pow(array[i], count);
    }
    if (sum == a)
    {
        return true;
    }
    return false;
}

int main()
{
    int n;
    int limit = pow(10, 9);
    int array[50];
    cin >> n;
    if (isArm(n, array))
    {
        cout << "True";
    }
    else
    {
        cout << "False";
    }
}