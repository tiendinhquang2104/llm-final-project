// S110.cpp : This file contains the 'main' function. Program execution begins and ends there.
//

#include <iostream>
#include<fstream>
#include<string>
#include<cstring>
using namespace std;
struct Date {
	int day, month, year;
	string era;
};
struct General
{
	string name, nationality;
	Date  born, death;
	int total_known_battles;
	string* known_battles;
};
struct Node
{
	General general;
	Node* next;
};

General* prob1(string filename, int& n)
{
	string c;
	ifstream fin;
	General* arr = new General[n];
	{
		fin.open(filename);
		getline(fin, c);
		while (getline(fin, c))
		{
			for (int i = 0; i < n; i++)
			{
				for (int j = 0; j < 9; j++)
				{
					if (j < 8)
					{
						getline(fin, c, ',');
						if (j == 1)
							arr[i].name = c;
						if (j == 2)
							arr[i].nationality = c;
						if (j == 3)
						{
							string backup;
							for (int k = 0; k < c.length(); k++)
							{
								if (c[k] == 'A' || c[k] == 'D' || c[k] == 'B' || c[k] == 'C')
									arr[i].born.era += c[k];
								else if (c[k] == ' ' || c[k] == '-');
								else
								{
									backup += c[k];
								}
								for (int f = 0; f < backup.length(); f++)
								{
									if (backup.length() >= 5)
									{
										arr[i].born.day = (backup[0] - '0') * 10 + (backup[1] - '0');
										arr[i].born.month = (backup[2] - '0') * 10 + (backup[3] - '0');
										arr[i].born.month = (backup[4] - '0') * 1000 + (backup[5] - '0') * 100 + (backup[6] - '0') * 10 + (backup[7] - '0');


									}
									if (j == 4)
									{
										string backup;
										for (int k = 0; k < c.length(); k++)
										{
											if (c[k] == 'A' || c[k] == 'D' || c[k] == 'B' || c[k] == 'C')
												arr[i].death.era += c[k];
											else if (c[k] == ' ' || c[k] == '-');
											else
											{
												backup += c[k];
											}

											if (backup.length() >= 5)
											{
												arr[i].death.day = (backup[0] - '0') * 10 + (backup[1] - '0');
												arr[i].death.month = (backup[2] - '0') * 10 + (backup[3] - '0');
												arr[i].death.month = (backup[4] - '0') * 1000 + (backup[5] - '0') * 100 + (backup[6] - '0') * 10 + (backup[7] - '0');


											}
										}
										if (j == 4)
										{
											int count = 0;
											string backup;
											for (int f = 0; f < c.length(); f++)
											{
												backup += c[f];
												if (c[f] == '|')
													count++;
											}
											string* str = new string[count + 1];
											int count2 = 0;
											for (int g = 0; g < c.length(); g++)
											{
												if (c[g] == '|')
													count++;
												else
												{
													str[count] += c[g];
												}
											}
											arr[i].known_battles = str;
											arr[i].total_known_battles = count + 1;
										}
									}
								}
							}
						}

					}
				}
			}
		}
		fin.close();
		return arr;

	}
}
Node* prob2(General* generals, int n)
{
	Node* head = nullptr;
	
	int count = 0;
	while (count < n)
	{
		Node* add = new Node;
		add->next = nullptr;
		if (head == nullptr)
		{
			add->general = generals[count];
			head = add;
		}
		else
		{
			Node* temp = head;
			while (temp->next != nullptr)
				temp = temp->next;
			add->general = generals[count];
			temp->next = add;
			if (temp->next == nullptr)
			{
				add->general = generals[count];
				temp->next = add;
			}
		}
		count++;
	} 
	return head;
}
void prob4(Node*& head, string nationality)
{
	if (head == nullptr)
		return;
	Node* temp = head;
	while (temp != nullptr)
	{
		if (temp->general.nationality == nationality)
		{
			Node* temp2 = temp;
			temp = temp->next;
			delete temp2;
		}
		else if (temp->next->general.nationality == nationality)
		{
			Node* temp2 = temp->next;
			temp->next = temp->next->next;
			delete temp2;
		}
		else
			temp = temp->next;
	}
}

int main()

{
	struct Date {
		int day, month, year;
		string era;
	};
	struct General
	{
		string name, nationality;
			Date  born, death;
			string total_known_battles;
			string* known_battles;
	};
	string c;
	ifstream fin;
	{
		fin.open("D:\50-best-european-generals-cleaned-first-20 (1).csv");
		getline(fin, c);
		cout << c;
		fin.close();

	}
}


