#include <iostream>
#include <cctype>
#include <string>
#include <fstream>
using namespace std;
int** inputMatrix(int&, int&, string);
void printMatrix(int**, int, int);
bool ismagicMatrix(int**, int, int);
bool rowEqual(int**, int, int);
bool colsEqual(int**, int, int);
int mainDigsum(int**, int, int);
int secondDigsum(int**, int, int);

int** inputMatrix(int& rows, int& cols, string filename) {
	ifstream fin(filename);
	fin >> rows >> cols;
	int** matrix = new int* [rows] {};
	for (int i = 0; i < rows; i++) {
		matrix[i] = new int[cols] {};
	}
	for (int i = 0; i < rows; i++) {
		for (int j = 0; j < cols; j++) {
			fin >> matrix[i][j];
		}
	}
	return matrix;
}

bool rowEqual(int** matrix, int rows, int cols) {
	int* sumRow = new int[rows] {};
	for (int i = 0; i < rows; i++) {
		for (int j = 0; j < cols; j++) {
			sumRow[i] = sumRow[i] + matrix[i][j];
		}
	}
	for (int i = 0; i < rows; i++) {
		for (int j = 0; j < rows; j++) {
			if (sumRow[i] != sumRow[j]) { return false; }
		}
	}
	return true;
}


bool colsEqual(int** matrix, int rows, int cols) {
	int* sumRow = new int[cols] {};
	for (int i = 0; i < cols; i++) {
		for (int j = 0; j < rows; j++) {
			sumRow[i] = sumRow[i] + matrix[i][j];
		}
	}
	for (int i = 0; i < cols; i++) {
		for (int j = 0; j < cols; j++) {
			if (sumRow[i] != sumRow[j]) { return false; }
		}
	}
	return true;
}
int mainDigsum(int** matrix, int rows, int cols) {
	int sumRow{};
	for (int i = 0; i < rows; i++) {
		sumRow += matrix[i][i];
	}
	return sumRow;
}

int secondDigsum(int** matrix, int rows, int cols) {
	int sumRow{};
	int idx = rows - 1;
	for (int i = 0; i < rows; i++) {
		sumRow += matrix[i][idx];
		idx--;
	}
	return sumRow;
}

bool ismagicMatrix(int** matrix, int rows, int cols) {
	bool row_and_col{};
	bool dig{};
	if (rowEqual(matrix, rows, cols) && colsEqual(matrix, rows, cols)) {
		row_and_col = true;
	}
	else {
		row_and_col = false;
	}
	if (mainDigsum(matrix, rows, cols) == secondDigsum(matrix, rows, cols)) {
		dig = true;
	}
	else {
		dig = false;
	}
	return dig && row_and_col;
}


void printMatrix(int** matrix, int rows, int cols) {
	for (int i = 0; i < rows; i++) {
		for (int j = 0; j < cols; j++) {
			cout << matrix[i][j] << " ";
		}
		cout << "\n";
	}
}
int main()
{
	ofstream fout("output.txt");
	int rows{}, cols{};
	int** matrix = inputMatrix(rows, cols, "input.txt");
	if (ismagicMatrix(matrix, rows, cols)) {
		fout << "true";
	}
	else {
		fout << "false";
	}
}
//3 3 1 2 3 4 5 6 7 8 9