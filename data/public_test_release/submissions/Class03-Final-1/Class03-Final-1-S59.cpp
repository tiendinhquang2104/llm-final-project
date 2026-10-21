#include <iostream>
#include <string>

int main() {
    std::string name {};
    std::string last_name {};

    std::cin >> name >> last_name;

    std::string best_subname = name.substr(0, 1);
    std::string best_sub_last_name = last_name.substr(0, 1);

    for (int i = 1; i < name.length(); i++) {
        std::string subname = name.substr(0, i+1);
        if (subname.back() < best_subname.back()) {
            best_subname = subname;
            continue;
        }

        break;
    }

    for (int i = 1; i < last_name.length(); i++) {
        std::string sub_last_name = last_name.substr(0, i+1);
        if (sub_last_name.back() < best_sub_last_name.back()) {
            best_sub_last_name = sub_last_name;
            continue;
        }

        break;
    }

    std::cout << best_subname << best_sub_last_name;
}
