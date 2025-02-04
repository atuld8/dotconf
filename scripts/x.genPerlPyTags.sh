#!/usr//bin/env bash

cd ${1:-.}

# Generate the ctags for specific path
ctags -R --languages=Python,Perl --exclude=.git --exclude=node_modules .

# Generate the list of perl or python files
find . -iname "*.py" -o -iname "*.pl" > cscope.files

# Generate the list of perl or python files
find . -iname "*.txt" -o -iname "*.md" -o -iname "*.json" -o -iname "*.ini" >> cscope.files

# Index the files using cscope command
cscope -b -q -k


