@REM @SET CYGPATH=C:\cygwin64
@REM @SET PERLPATH=C:\Strawberry\perl\bin
@REM @SET VIMPASS=
@REM @SET GIT_USER=
@REM @SET GIT_SERVER=
@REM @SET CFG_EDITOR=vim/gvim/type/notepad
@REM @SET GIT_STATUS_LEVEL=0/1/2/3
@REM @SET GIT_CMD_USED=
@REM @SET OPEN_CMD=explorer/start
@REM @SET ETRACK_CLI_PATH=

@REM @echo Initializing... This may take some time...
@echo off && call %userprofile%\.vim\wincmds\alias_global.cmd %*
@REM echo off && call %userprofile%\.vim\wincmds\alias_dotconf.cmd %*

@REM echo off && call %userprofile%\.vim\wincmds\alias_bldbx.cmd %*

@REM echo off && call %userprofile%\.vim\wincmds\alias_nbu.cmd %*
@REM echo off && call %userprofile%\.vim\wincmds\alias_bmr.cmd %*
@REM echo off && call %userprofile%\.vim\wincmds\alias_nbu_special.cmd %*
@REM echo off && call %userprofile%\.vim\scripts\definstallpathsmacro.cmd %*
@REM echo off && call %userprofile%\.vim\wincmds\alias_sf.cmd %*

@REM echo off && call %userprofile%\.vim\wincmds\alias_ps.cmd %*

@IF EXIST %userprofile%\alias.tmp call %userprofile%\alias.tmp %*
@IF EXIST %userprofile%\alias.loc.cmd call %userprofile%\alias.loc.cmd %*

@IF "%1" == "QUICK_ACCESS" DOSKEY /MACROFILE=%userprofile%\alias.doskey

@REM @SET PATH=%PATH%;
@REM PATH FOR WGET command on windows
@REM @SET PATH=%PATH%;C:\Program Files (x86)\GnuWin32\bin;

@REM Clear the screen
@REM cls


