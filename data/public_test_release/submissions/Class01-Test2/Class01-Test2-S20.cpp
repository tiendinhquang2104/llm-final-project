#include<iostream>
#include<vector>
#include<string>
#include<fstream>
using namespace std;

struct Date {
	int day, month, year;
	string era;
};
struct General {
	string name, nationality;
	Date born, death;
	vector<string> known_battles;
};
struct Node {
	General general;
	Node* left;
	Node* right;
};
vector<General> porb1(string filename)
{
	string h;
	vector<General> output;
	ifstream fin;
	fin.open(filename);
	getline(fin, h);
	while (getline(fin, h))
	{
		General making;
		string holding;
		vector<string> hold;
		for (char c : h)
		{
			if (c == ',')
			{
				hold.push_back(holding);
				holding = "";
			}
			else
				holding += c;
			hold.push_back(holding);
		}
		making.name = hold[0];
		making.nationality = hold[1];
		//age splicing
		 holding = hold[2];
		vector<string> hold1;
		for (char c : holding)
		{
			if (c == ' ')
			{
				hold1.push_back(holding);
				holding = "";
			}
			else
				holding += c;
			hold1.push_back(holding);
		}
		making.born.era = hold1[1];
		//day splicing
		 holding = hold1[0];
		vector<string> hold2;
		for (char c : holding)
		{
			if (c == ' ')
			{
				hold2.push_back(holding);
				holding = "-";
			}
			else
				holding += c;
			hold2.push_back(holding);
			making.born.day = stoi(hold2[0]);
			making.born.month = stoi(hold2[1]);
			making.born.year = stoi(hold2[2]);




			 holding = hold[3];
			vector<string> hold1;
			for (char c : holding)
			{
				if (c == ' ')
				{
					hold1.push_back(holding);
					holding = "";
				}
				else
					holding += c;
				hold1.push_back(holding);
			}
			making.death.era = hold1[1];
			//day splicing
			 holding = hold1[0];
			vector<string> hold2;
			for (char c : holding)
			{
				if (c == ' ')
				{
					hold2.push_back(holding);
					holding = "-";
				}
				else
					holding += c;
				hold2.push_back(holding);
				making.death.day = stoi(hold2[0]);
				making.death.month = stoi(hold2[1]);
				making.death.year = stoi(hold2[2]);
			}




			 holding = hold[4];
			vector<string> hold3;
			for (char c : holding)
			{
				if (c == '|')
				{
					hold3.push_back(holding);
					holding = "";
				}
				else
					holding += c;
				hold3.push_back(holding);
			}
			for (int a = 0; a < hold3.size(); a++)
				making.known_battles[a] = hold3[a];

			output.push_back(making);
		}

		
	}
	fin.close();


	return output;
};
Node* insert(Node*& root,General general)
{
	Node* newnode = new Node ;
	 newnode->general= general;
	 if (root == nullptr)
		 return newnode;
	 
		 int a, b;
		 if (root->general.born.era == "BC")
			 a = 0;
		 if (root->general.born.era == "AD")
			 a = 1;
		 if (root->general.born.era == "BC")
			 b = 0;
		 if (root->general.born.era == "AD")
			 b = 1;

		 if (general.born.year < root->general.born.year)
		 {
			 insert(root->left, general);
		 }
		 if (general.born.year > root->general.born.year)
		 {
			 insert(root->right, general);

		 }
		 else
		 {
			 if (general.born.month < root->general.born.month)
			 {
				 insert(root->left, general);
			 }
			 if (general.born.month > root->general.born.month)
			 {
				 insert(root->right, general);
			 }
			 else
			 {
				 if (general.born.day < root->general.born.day)
				 {
					 insert(root->left, general);
				 }
				 if (general.born.day > root->general.born.day)
				 {
					 insert(root->right, general);
				 }
				 else
				 {
					 if (general.death.year < root->general.death.year)
					 {
						 insert(root->left, general);
					 }
					 if (general. death.day > root->general.death.day)
					 {
						 insert(root->right, general);
					 }
					 else
					 {
						 if (general.death.month < root->general.death.month)
						 {
							 insert(root->left, general);
						 }
						 if (general.death.month > root->general.death.month)
						 {
							 insert(root->right, general);
						 }
						 else
							 if (general.death.day < root->general.death.day)
							 {
								 insert(root->left, general);
							 }
						 if (general.death.day > root->general.death.day)
						 {
							 insert(root->right, general);
						 }
					 }
				 }
			 }





		 }
}
		 Node* prob2(vector<General> general)
		 {
			 Node* root = new Node;
			 root->general = general[0];
			 for (int i = 1; i < general.size(); i++)
			 {
				 insert(root, general[i]);
			 }
			 return root;
		 };





int main()
{

}