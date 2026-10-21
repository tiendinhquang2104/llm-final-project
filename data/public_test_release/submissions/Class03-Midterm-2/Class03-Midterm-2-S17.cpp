#include <iostream>
#include <vector>
#include <unordered_set>
using namespace std;

int main()
{
    int n;
    cin >> n;
    vector<int> arr(n);
    for (int i = 0; i < n; i++)
    {
        cin >> arr[i];
    }

    unordered_set<int> seen;
    vector<int> unique;

    for (int i = 0; i < n; i++)
    {
        if (seen.find(arr[i]) == seen.end())
        {
            seen.insert(arr[i]);
            unique.push_back(arr[i]);
        }
    }

    cout << unique.size() << endl;

    for (int i = 0; i < unique.size(); i++)
    {
        cout << unique[i] << " ";
    }
    cout << endl;

    return 0;
}
