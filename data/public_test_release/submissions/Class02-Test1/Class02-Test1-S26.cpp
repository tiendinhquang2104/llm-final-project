include <iostream>
include <sstream>
include <fstream>
include <string>
struct Battle{
	string name, location;
	string from_date, to_date;
	int total_famous_generals;
	string* list_famous_generals;
	
};
Battle battlesinfo(){
	string line;
	Battle e;
	getline(e.name,line);
	getline(e.location,line);
	getline(e.from_date,line);
	getline(e.to_date,line);
	getline(e.list_famous_generals,line,;);
	return e;
	
}
Battle* probi(string filename, int& n){
	ifstream fin(filename);
	string line;
	getline(fin, line);
	fin.clear();
	fin.searchg(0);
	getline(fin,line);
	Battle* list= new battlelist[];
	for( int i=0,i<n,i++){
			battlelist[i]=getline(fin,line);
}
	for( int i=0,i<n,i++){
			battlelist[i]=battlesinfo();
}
	return battlelist[];
	
}

