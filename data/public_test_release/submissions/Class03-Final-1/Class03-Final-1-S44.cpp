#include <iostream>
#include <fstream>

int main()
{
    std::string ten;
    std::string ho;
    std::cin >> ten >> ho;

    std::string res = "";
    std::string temp = "";

    int tenLen = ten.length();
    int hoLen = ho.length();

    for (int i = 0; i < tenLen; i++)
    {
        temp += ten[i];
        std::string copy = temp;
        for (int j = 0; j < hoLen; j++)
        {
            std::string subHo = ho.substr(0, j + 1);
            temp += subHo;
            if (res == "")
            {
                res = temp;
            }
            if (temp < res)
            {
                res = temp;
            }
        }
        temp = copy;
    }

    std::cout << res;

    return 0;
}