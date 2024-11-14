#!/bin/env bash

cd $1

# Generate the ctags for specific path
ctags -R --languages=Python,Perl --exclude=.git --exclude=node_modules .

# Generate the list of perl or python files
find . -name "*.py" -o -name "*.pl" > cscope.files

# Index the files using cscope command
cscope -b -q -k


