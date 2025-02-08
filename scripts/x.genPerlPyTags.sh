#!/usr//bin/env bash

cd ${1:-.}

# Generate the ctags for specific path
ctags -R --languages=Python,Perl --exclude=.git --exclude=node_modules .

# Generate the list of perl or python files
find . -iname "*.py" -o -iname "*.pl" > cscope.files

# Generate the list of scripts
find . -iname "*.sh" -o  -iname "*.bat" -o -iname "*.cmd" >> cscope.files

# Generate the list of other files
find . -iname "*.txt" -o -iname "*.md" -o -iname "*.json" -o -iname "*.ini" -o -iname "*.xml" -o -iname "*.html" >> cscope.files

# Index the files using cscope command
rm -f cscope.out cscope.in.out cscope.po.out

cscope -b -q -k -v -i cscope.files -f cscope.out
