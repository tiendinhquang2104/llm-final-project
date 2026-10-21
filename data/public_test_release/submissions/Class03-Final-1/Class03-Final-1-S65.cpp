#include <iostream>
#include <string>

bool is_lesser(std::string s1, std::string s2)
{
    for (int i = 0; i < std::min(s1.size(), s2.size()); ++i)
    {
        if (s1[i] < s2[i])
        {
            return true;
        };
        if (s1[i] > s2[i])
        {
            return false;
        };
    };
    if (s1.size() < s2.size())
        return true;
    return false;
};

std::string min_username(std::string s1, std::string s2)
{
    std::string return_username = s1 + s2;
    for (int i = 0; i < s1.size(); ++i)
    {
        for (int j = 0; j < s2.size(); ++j)
        {
            std::string t_username = s1.substr(0, i + 1) + s2.substr(0, j + 1);
            if (!is_lesser(return_username, t_username))
            {
                return_username = t_username;
            };
        };
    };
    return return_username;
};

int main()
{
    std::string firstname, lastname;
    std::cin >> firstname >> lastname;
    std::cout << min_username(firstname, lastname);
    return 0;
};