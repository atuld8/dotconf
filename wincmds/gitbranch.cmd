@echo off

@REM http://www.hanselman.com/blog/ABetterPROMPTForCMDEXEOrCoolPromptEnvironmentVariablesAndANiceTransparentMultiprompt.aspx
@REM
set GITBRANCH=
set TRACKED_CHANGE=0
set UNTRACKED_CHANGE=0
set REMOTE_STATUS=Ok

:: Check for administrative privileges
net session >nul 2>&1
IF %errorlevel%==0 (
    @IF defined CLINK_DIR (
       SET "SPECIAL_PRMPT_DATA_EX=%SPECIAL_PRMPT_DATA%$E[31mA$S$E[0m"
    ) ELSE (
       SET "SPECIAL_PRMPT_DATA_EX=%SPECIAL_PRMPT_DATA%A$S"
    )
) ELSE (
    @IF defined CLINK_DIR (
       SET "SPECIAL_PRMPT_DATA_EX=%SPECIAL_PRMPT_DATA%$E[0m"
    ) ELSE (
       SET "SPECIAL_PRMPT_DATA_EX=%SPECIAL_PRMPT_DATA%"
    )
)

SET COMPUTERDETAILS=%COMPUTERNAME%
IF "%USE_IP_IN_PROMPT%" == "1" (
   FOR /f "tokens=2 delims=:" %%I in ('ipconfig ^| findstr /c:"IPv4 Address"') do @SET "COMPUTERDETAILS=%COMPUTERNAME%%%I"
)

@IF NOT DEFINED GIT_STATUS_LEVEL @SET GIT_STATUS_LEVEL=0

IF %GIT_STATUS_LEVEL% LSS 0 GOTO END_OF_SCRIPT

IF %GIT_STATUS_LEVEL% EQU 0 GOTO PRINT_PROMPT_WITHOUT_GIT_FULL_STATUS

for /f "tokens=1,*" %%I in ('git.exe branch 2^> NUL ^| findstr /b "* "') do set  GITBRANCH=%%J
for /f "tokens=2* delims=()" %%I in ('echo "%GITBRANCH%"') do set  GITBRANCH=%%I

IF "%GITBRANCH%" == "" GOTO :PRINT_PROMPT_WITHOUT_GIT_FULL_STATUS

IF NOT "%GITBRANCH%" == "" for /F %%i in ('git config --get remote.origin.url 2^>NUL') do SET REPONAME=%%~ni
set FINAL_GITBRANCH=%REPONAME% @%GITBRANCH%

IF %GIT_STATUS_LEVEL% LSS 2 GOTO PRINT_PROMPT_WITHOUT_GIT_FULL_STATUS

SET FINAL_GITBRANCH=%REPONAME% @%GITBRANCH%.
git diff-files --no-ext-diff --quiet > NUL
IF %ERRORLEVEL% NEQ 0 SET FINAL_GITBRANCH=%REPONAME% @%GITBRANCH%*

IF %GIT_STATUS_LEVEL% LSS 3 GOTO PRINT_PROMPT_WITHOUT_GIT_FULL_STATUS

for /f "tokens=1" %%I in ('git.exe status --untracked-files^=no --porcelain 2^>NUL ^| %SystemRoot%\system32\find /v /c ^"^"') do set  TRACKED_CHANGE=%%I
for /f "tokens=1" %%I in ('git.exe status --porcelain 2^>NUL ^| %SystemRoot%\system32\find /v /c ^"^"') do set /a "UNTRACKED_CHANGE=%%I-%TRACKED_CHANGE%"

@REM Your branch is behind 'origin/master' by 26 commits, and can be fast-forwarded.
@REM Your branch is ahead of 'origin/master' by 1 commit.
@REM Your branch is up-to-date with 'origin/master'.
@REM Your branch and 'origin/master' have diverged,
@REM and have 1 and 1 different commits each, respectively.


for /f "tokens=1-9" %%I in ('git.exe status origin 2^>NUL') do (
      if "%%I %%J " == "Your branch " (
             if "%%L" == "behind" (
                 SET REMOTE_STATUS=Pull
             )

             if "%%L" == "ahead" (
                 SET REMOTE_STATUS=Push
             )

             if "%%N" == "diverged," (
                 SET REMOTE_STATUS=Merge
             )
      )
)


set FINAL_GITBRANCH=%REPONAME% @%GITBRANCH% T:+%TRACKED_CHANGE% UT:+%UNTRACKED_CHANGE% RS:%REMOTE_STATUS%

:PRINT_PROMPT_WITHOUT_GIT_FULL_STATUS

@REM COLOR http://ascii-table.com/ansi-escape-sequences.php
@IF "%MY_PROMPT_SHOULD_BE_SIMPLE%" == "9" GOTO END_OF_SCRIPT

@IF "%MY_PROMPT_SHOULD_BE_SIMPLE%" == "1" (
    prompt $C$D$S$T$F$S$M[%COMPUTERDETAILS%]$S$P$S$_%SPECIAL_PRMPT_DATA_EX%Cmd$+$$$S
) ELSE (
    @IF "%GITBRANCH%" == "" (
        @IF defined ConEmuDir (
            prompt $C$D$S$T$F$S$E[m$E[32m$E]9;8;"USERNAME"$E\@$E]9;8;"COMPUTERDETAILS"$E\$S$P$S$E[0m$_Cmd$S$$$S
            prompt $C$D$F$S$M[%COMPUTERDETAILS%]$S$P$S$_$T$SCmd$+$$$S
        ) ELSE (

            @IF defined CLINK_DIR (
                prompt $E[33m$C$D$S$T$F$S$E[32m$M$E[m$E[36m[%COMPUTERDETAILS%]$E[32m$S$P$S$_$E[33m%SPECIAL_PRMPT_DATA_EX%Cmd$+$$$S$E[0m
            ) ELSE (
                prompt $C$D$S$T$F$S$M[%COMPUTERDETAILS%]$S$P$S$_%SPECIAL_PRMPT_DATA_EX%Cmd$+$$$S
            )
        )
    ) ELSE (

        @IF defined ConEmuDir (
            prompt $C$D$S$T$F$S$P$S$C$E[1;7;32;47m%FINAL_GITBRANCH%$E[0m$F $G
            prompt $C$D$S$T$F$S$E[m$E[32m$E]9;8;"USERNAME"$E\@$E]9;8;"COMPUTERDETAILS"$E\$S$E[92m$P$S$C$E[1;7;32;47m%FINAL_GITBRANCH%$E[0m$F$_%SPECIAL_PRMPT_DATA_EX%$SCmd$S$$$S
        ) ELSE (
        @IF defined CLINK_DIR (
            prompt $E[33m$C$D$S$T$F$S$E[32m$M$E[m$E[36m[%COMPUTERDETAILS%]$E[32m$S$P$S$E[33m$C%FINAL_GITBRANCH%$F$_$E[33m%SPECIAL_PRMPT_DATA_EX%Cmd$+$$$S$E[0m
        ) ELSE (
            prompt $C$D$S$T$F$S$M[%COMPUTERDETAILS%]$S$P$S$C%FINAL_GITBRANCH%$F$_%SPECIAL_PRMPT_DATA_EX%Cmd$+$$$S
            )
        )
    )
)

:END_OF_SCRIPT
