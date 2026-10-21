#include <iostream>

int n;
int arr[10001];
int modified_arr[10001];

int main() {
    std::cin >> n;

    for (int i = 0; i < n; i++) {
        std::cin >> arr[i];
    }

    int modified_arr_idx = 1;
    modified_arr[0] = arr[0];

    for (int i = 1; i < n; i++) {
        bool is_duplicate = false;
        for (int j = 0; j < modified_arr_idx; j++) {
            if (arr[i] == modified_arr[j]) {
                is_duplicate = true;
                break;
            }
        }

        if (is_duplicate) continue;
        modified_arr[modified_arr_idx] = arr[i];
        modified_arr_idx++;
    }

    std::cout << modified_arr_idx << '\n';
    for (int i = 0; i < modified_arr_idx; i++) {
        std::cout << modified_arr[i] << ' ';
    }

    return 0;
}
