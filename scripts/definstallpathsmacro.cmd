@ECHO OFF

@IF "%1" == "QUICK_ACCESS" GOTO QA_ALIAS_DEFINE_INSTALLPATH_MACRO

@IF NOT DEFINED PSTN_MOUNT_DRIVE @SET PSTN_MOUNT_DRIVE=N:

@IF "%1" == "" GOTO DEFINE_MACROS

@SETLOCAL enabledelayedexpansion

@FOR /F "usebackq tokens=1-3 delims=|" %%A IN ("%~dp0definstallpaths.data") DO @IF NOT "%%A"=="" @IF NOT "%%A"=="#" ( @SET "VER_ID[%%A]=%%B"& @SET "BLD_ID[%%A]=%%C" )
@SET VER_ID[0]=0
@SET BLD_ID[0]=0000

@IF "%1" == "" GOTO END_SCRIPT

@IF "%1" == "LAUNCH" GOTO LAUNCH_SETTING
@IF "%1" == "ECHO" GOTO ECHO_SETTING
@IF "%1" == "LIST" GOTO LIST_SETTING
@IF "%1" == "LISTSJA" GOTO LIST_SJA

:LAUNCH_SETTING
@SET ID=%2
@SET TYPE=%3
@IF "!VER_ID[%ID%]!" == "" @SET "ID=0" && @SET "VER_ID[0]=%2" && @SET "BLD_ID[0]=%3" && @SET TYPE=%4

@SET ARGUMENT=x64\SETUP.EXE %TYPE%
@IF "%ID%" == "80" (
	@IF "%TYPE%" == "/SERVER" ( @SET ARGUMENT=x64\SETUP.EXE ) ELSE ( @SET ARGUMENT=PC_clnt\x64\SETUP.EXE )
)
@IF "%ID%" == "81" (
	@IF "%TYPE%" == "/SERVER" ( @SET ARGUMENT=x64\SETUP.EXE ) ELSE ( @SET ARGUMENT=PC_clnt\x64\SETUP.EXE )
)
GOTO MAIN_LOOP

:ECHO_SETTING
@SET ID=%2
@IF "!VER_ID[%ID%]!" == "" @SET "ID=0" && @SET "VER_ID[0]=%2" && @SET "BLD_ID[0]=%3"
GOTO MAIN_LOOP

:MAIN_LOOP
@SET "BUILD_PATH=%PSTN_MOUNT_DRIVE%\NB\!VER_ID[%ID%]!\NB_!VER_ID[%ID%]!_!BLD_ID[%ID%]!\NetBackup_!VER_ID[%ID%]!_Win"

@IF "%1" == "ECHO" @ECHO %BUILD_PATH%& GOTO END_SCRIPT

@ECHO %BUILD_PATH%\%ARGUMENT%
START %BUILD_PATH%\%ARGUMENT%
GOTO END_SCRIPT

:LIST_SETTING
@SET ID=%2
@IF "!VER_ID[%ID%]!" == "" @SET "ID=0" && @SET "VER_ID[0]=%2" && @SET "BLD_ID[0]=%3"
for /F "tokens=*" %%A in ('dir /O /b %PSTN_MOUNT_DRIVE%\NB\!VER_ID[%ID%]!') do @ECHO %PSTN_MOUNT_DRIVE%\NB\!VER_ID[%ID%]!\%%A
GOTO END_SCRIPT

:LIST_SJA
@SET ID=%2
@IF "!VER_ID[%ID%]!" == "" @SET "ID=0" && @SET "VER_ID[0]=%2" && @SET "BLD_ID[0]=%3"
@for /f %%d in ('dir /b %PSTN_MOUNT_DRIVE%\NB\!VER_ID[%ID%]!\NB_!VER_ID[%ID%]!_!BLD_ID[%ID%]!\NetBackup_!VER_ID[%ID%]!_VU_*') DO  @FORFILES /S /P %PSTN_MOUNT_DRIVE%\NB\!VER_ID[%ID%]!\NB_!VER_ID[%ID%]!_!BLD_ID[%ID%]!\%%d  /C "cmd /c @echo @path" /M "*.sja"
GOTO END_SCRIPT

:DEFINE_MACROS
@DOSKEY m.bld..rf=for /F "tokens=*" %%A in ('dir /O /b %PSTN_MOUNT_DRIVE%\NB\$1') do @ECHO %PSTN_MOUNT_DRIVE%\NB\$1\%%A
@DOSKEY m.sja..rf.b=@for /f %%d in ('dir /b %PSTN_MOUNT_DRIVE%\NB\$1\NB_$1_$2\NetBackup_$1_VU_*') DO  @FORFILES /S /P %PSTN_MOUNT_DRIVE%\NB\$1\NB_$1_$2\%%d  /C "cmd /c @echo @path" /M "*.sja"
@DOSKEY m.bld..rs==%~dpnx0 LIST $*
@DOSKEY m.sja..rs==%~dpnx0 LISTSJA $*

@DOSKEY m.bld..rs.t=%~dpnx0 LAUNCH $*
@DOSKEY m.bld..rf.b.t=%~dpnx0 LAUNCH $*

@DOSKEY cp.bld..rs=%~dpnx0 ECHO $*^|clip
@DOSKEY cp.bld..rf.b=%~dpnx0 ECHO $*^|clip


@DOSKEY m.bld..oc=@IF NOT EXIST "%SystemDrive%\nbtestdata\OC_$1_Server" (@xcopy B:\OpsCenter\$1\CURRENT\DVD\OpsCenter_$1_Win\x64\Server %SystemDrive%\nbtestdata\OC_$1_Server /E /I /F /H /Y ^&^& %SystemDrive%\nbtestdata\OC_$1_Server\SETUP.EXE) ELSE (%SystemDrive%\nbtestdata\OC_$1_Server\SETUP.EXE )
@DOSKEY cp.bld..oc=echo B:\OpsCenter\$1\CURRENT\DVD\OpsCenter_$1_Win\x64\Server^|clip

:QA_ALIAS_DEFINE_INSTALLPATH_MACRO

:END_SCRIPT


