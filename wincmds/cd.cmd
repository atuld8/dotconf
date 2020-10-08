@echo off

if '%1'=='' cd & goto GetGitBranch

if '%1'=='-' (
    cd /d %OLDPWD%
    set OLDPWD="%cd%"
) else (
    if '%1'=='..' (
        if "%2"=="" (
            cd ..
        ) else if "%2"=="2" (
           cd ..\..\%3
        ) else if "%2"=="3" (
           cd ..\..\..\%3
        ) else if "%2"=="4" (
            cd ..\..\..\..\%3
        ) else if "%2"=="5" (
            cd ..\..\..\..\..\%3
        ) else if "%2"=="6" (
            cd ..\..\..\..\..\..\%3
        ) else if "%2"=="7" (
            cd ..\..\..\..\..\..\..\%3
        ) else if "%2"=="8" (
            cd ..\..\..\..\..\..\..\..\%3
        ) else if "%2"=="9" (
            cd ..\..\..\..\..\..\..\..\..\%3
        ) else (
            cd ..\%2
        )

        if not errorlevel 1 set OLDPWD="%cd%"
    ) else (
        if '%1'=='/d' (
           cd %*
        ) else (
           cd /d %*
        )
        if not errorlevel 1 set OLDPWD="%cd%"
    )
)


:GetGitBranch

call %~dp0gitbranch.cmd

goto :EOF

