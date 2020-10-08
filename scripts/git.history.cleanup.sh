#!/bin/sh
# https://tecadmin.net/delete-commit-history-in-github/
#

# Create Orphan Branch
git checkout --orphan tempBranch

# Check for the status of the files
git status

# Git add all which is present in the branch 
# git add -A 

# Commit this as first commit
git commit -am "cleanup the history and first commit"

# Delete the master branch
git branch -D master

# Rename the current branch to master branch
git branch -m master

# push the changes to remote
git push -f origin master
