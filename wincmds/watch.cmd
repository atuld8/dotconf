@ECHO OFF
@REM EX: set es=echo. ^^^& echo  -------------------------------------- ^^^& echo.
@REM EX: x.watch "nbstlutil report ^& %es% ^& nbstlutil dump  -subsys 8 ^& %es% ^& nbstlutil stlilist"
@REM EX: x.watch tasklist ^^^| findstr SETUP
@REM EX: x.watch nbstlutil report
@REM EX: x.watch -n 10 nbstlutil report
@REM EX: x.watch -n 10 "nbstlutil report ^& %es% ^& nbstlutil dump  -subsys 8 ^& %es% ^& nbstlutil stlilist"
@REM EX: x.watch -n -1 <cmd>
@REM EX: x.watch -c # <cmd>

SETLOCAL EnableDelayedExpansion

SET LOOP_COUNTER=-1
SET WAIT_IN_SEC=5
SET PROCESS_TO_RUN=%*
SET RANDOM_FILE_NAME=%RANDOM%
SET TEMP_FILE=%temp%\%RANDOM_FILE_NAME%

SET firstChar=%PROCESS_TO_RUN:~0,1%
SET firstChar=%firstChar:"=+%

IF "%firstChar%" == "+" GOTO FOR_LOOP

IF "%1" == "" GOTO ERROR

IF NOT "%1" == "-n" (
   IF NOT "%1" == "-c" GOTO LOOP
)

IF "%1" == "-c" SET LOOP_COUNTER=%2
IF "%1" == "-n" SET WAIT_IN_SEC=%2

FOR /f "tokens=1,2,* delims= " %%a IN ("%*") DO SET PROCESS_TO_RUN=%%c

IF "!PROCESS_TO_RUN!" == "" GOTO ERROR
goto LOOP

:FOR_LOOP
FOR /f "tokens=* delims= " %%a IN ("%*") DO SET PROCESS_TO_RUN=%%a
GOTO LOOP

:LOOP
  CMD /c !PROCESS_TO_RUN! >%TEMP_FILE% 2>&1
  CLS

  IF "%1" == "-c" ECHO [ WAIT_TIME(s): %WAIT_IN_SEC% ] [ CMD: !PROCESS_TO_RUN! ] [ CMD_EXECUTED_TIME: (%DATE% %TIME%) ] [ COUNTER: %LOOP_COUNTER% ] [ TEMP_FILE_NAME: %RANDOM_FILE_NAME% ]
  IF NOT "%1" == "-c" ECHO [ WAIT_TIME(s): %WAIT_IN_SEC% ] [ CMD: !PROCESS_TO_RUN! ] [ CMD_EXECUTED_TIME: (%DATE% %TIME%) ] [ TEMP_FILE_NAME: %RANDOM_FILE_NAME% ]

  ECHO.
  ECHO.
  TYPE %TEMP_FILE%

  IF "%WAIT_IN_SEC%" == "-1"  TIMEOUT /t %WAIT_IN_SEC%
  IF NOT "%WAIT_IN_SEC%" == "-1" TIMEOUT /t %WAIT_IN_SEC% > NUL

  IF %LOOP_COUNTER% EQU 1 GOTO :EOF
  IF NOT %LOOP_COUNTER% EQU -1 SET /A LOOP_COUNTER=%LOOP_COUNTER% - 1

  GOTO LOOP


:ERROR
  ECHO "No command line specified"
  ECHO "Usage: watch.cmd [-n [time in sec] ^| -c [counter]] valid command line"
ENDLOCAL
