@ECHO OFF
@SETLOCAL EnableDelayedExpansion

@REM /*vim :set iskeywords+=% */
IF "%1" == "" GOTO HELP

GOTO %1

:HELP
@ECHO "Script ACTION Action_Args..."
@ECHO "FIRST PARAMETER IS ACTION"
@ECHO "ADD_EEB_TAG"

@ENDLOCAL
GOTO FINAL_CLEANUP


:ADD_EEB_TAG
IF "%2" == "" @SET /P "EEB_VER=Enter EEB Version : "
IF NOT "%2" == "" @SET EEB_VER=%2

@FOR /f "tokens=2" %%a in ('git branch ^| findstr "* "') do (
        SET EEB_ET=%%a
        SET EEB_ET1=!EEB_ET:EEB/ET=!
        @ECHO git tag -a  EEB_et!EEB_ET1!_v%EEB_VER% -m "EEB Version %EEB_VER%"
        @ECHO git push origin EEB_et!EEB_ET1!_v%EEB_VER%
        git log -1
)
GOTO FINAL_CLEANUP

:OPEN_COMMIT_MSG_FILE
@FOR /f %%d IN ('git rev-parse --show-toplevel') DO SET GIT_BASE_DIR=%%d

@FOR /f "tokens=2" %%a in ('git branch ^| findstr "* "') do (
        SET EEB_ET=%%a
        SET EEB_ET1=!EEB_ET:EEB/ET=/ET!
        SET EEB_ET1=!EEB_ET1:BUGFIX/ET=/ET!
        SET EEB_ET1=!EEB_ET1:FEATURE/ET=/ET!
        SET EEB_ET1=!EEB_ET1:/ET=!
        SET EEB_AFTER_DOT=!EEB_ET1:*.=.!
	CALL SET EEB_ET1=%%EEB_ET1:!EEB_AFTER_DOT!=%%
        SET CMTMSG_FILE=!GIT_BASE_DIR!/../!EEB_ET1!%3.cmtmsg
        @ECHO ON
        IF  /I "%2" == "p" @ECHO !CMTMSG_FILE!
        @ECHO OFF
        SET ADD_DATA_TO_FILE=1
        @IF EXIST !CMTMSG_FILE! SET ADD_DATA_TO_FILE=0
        @IF "!ADD_DATA_TO_FILE!" == "1" @ECHO.>>!CMTMSG_FILE!
        @IF "!ADD_DATA_TO_FILE!" == "1" @ECHO.>>!CMTMSG_FILE!
        @IF "!ADD_DATA_TO_FILE!" == "1" @ECHO Incident:!EEB_ET1!>>!CMTMSG_FILE!
        IF  /I "%2" == "o" %CFG_EDITOR% !CMTMSG_FILE!

)
GOTO FINAL_CLEANUP

:EXECUTION_TIME
@REM output of icacls is to NUL
@REM cmd.time "icacls "E:\Program Files\Veritas\NetBackup\Logs\user_ops" /remove:g *S-1-1-0 /t ^>NUL"
@REM output of icacls is to stdout
@REM cmd.time icacls "E:\Program Files\Veritas\NetBackup\Logs\user_ops" /remove:g *S-1-1-0 /t
@REM output of cmd.time is to NUL
@REM cmd.time icacls "E:\Program Files\Veritas\NetBackup\Logs\user_ops" /remove:g *S-1-1-0 /t > NUL

FOR /f "tokens=1,* delims= " %%a IN ("%*") DO SET PROCESS_TO_RUN=%%b
SET firstChar=%PROCESS_TO_RUN:~0,1%
SET firstChar=%firstChar:"=+%

IF "%firstChar%" == "+"  FOR /f "tokens=* delims= " %%a IN (!PROCESS_TO_RUN!) DO SET PROCESS_TO_RUN=%%a

@ECHO  Cmd$ !PROCESS_TO_RUN!
SET START_DATE=%DATE%
SET START_TIME=%TIME%
SET "startTime=%time: =0%"

%PROCESS_TO_RUN%

SET END_DATE=%DATE%
SET END_TIME=%TIME%
SET "endTime=%time: =0%"

SET "end=!endTime:%time:~8,1%=%%100)*100+1!"  &  set "start=!startTime:%time:~8,1%=%%100)*100+1!"
SET /A "elap=((((10!end:%time:~2,1%=%%100)*60+1!%%100)-((((10!start:%time:~2,1%=%%100)*60+1!%%100)"

@REM Convert elapsed time to HH:MM:SS:CC format:
SET /A "cc=elap%%100+100,elap/=100,ss=elap%%60+100,elap/=60,mm=elap%%60+100,hh=elap/60+100"

@ECHO Start_Date_Time = !START_DATE! !START_TIME!
@ECHO End_Date_Ttime  = !END_DATE! !END_TIME!
@ECHO Elapsed_time    = %hh:~1%%time:~2,1%%mm:~1%%time:~2,1%%ss:~1%%time:~8,1%%cc:~1%
GOTO FINAL_CLEANUP

:CD_TO_PUSHD_MACROS
@ECHO @ECHO OFF>%temp%/pushd_alias.cmd
@FOR /f "tokens=*" %%a in ('DOSKEY /MACROS ^| findstr "^cd\..*=" ^| findstr /v "gbase"') do (
       SET "CD_CMD_FILTER=%%a"
       SET CD_CMD=!CD_CMD_FILTER:\$*=\!
       SET PUSHD_CMD=!CD_CMD:%~dp0cd.cmd=%~dp0pushd.cmd!
       SET ALIAS_PUSHD=!PUSHD_CMD:cd.=pd.!
       SET CLEAN_ALIAS_PUSHD=!ALIAS_PUSHD_CMD:!
       @ECHO !ALIAS_PUSHD!
       @ECHO DOSKEY !ALIAS_PUSHD!>>%temp%/pushd_alias.cmd
)

GOTO FINAL_CLEANUP

:FINAL_CLEANUP
@ENDLOCAL
GOTO :EOF
