#include <iostream>
#include <vector>
#include <set> // For std::set

void removeDuplicatesUsingSet(std::vector<int>& arr) {
    std::set<int> uniqueElements(arr.begin(), arr.end());
    arr.assign(uniqueElements.begin(), uniqueElements.end());
}

int main() {
    std::vector<int> numbers = {1, 2, 2, 3, 4, 4, 5, 1};
    std::cout << "Original array: ";
    for (int num : numbers) {
        std::cout << num << " ";
    }
    std::cout << std::endl;

    removeDuplicatesUsingSet(numbers);

    std::cout << "Array after removing duplicates: ";
    for (int num : numbers) {
        std::cout << num << " ";
    }
    std::cout << std::endl;

    return 0;
}