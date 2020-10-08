@echo off

if '%1'=='popd' popd & goto GetGitBranch

pushd %*


:GetGitBranch

call %~dp0gitbranch.cmd

goto :EOF

