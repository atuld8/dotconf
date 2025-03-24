@IF EXIST %userprofile%\set.var.cmd call %userprofile%\set.var.cmd %*
@IF EXIST %userprofile%\set.vrts.cmd call %userprofile%\set.vrts.cmd %*

@REM @echo Initializing... This may take some time...
@echo off && call %userprofile%\.vim\wincmds\alias_global.cmd %*
@REM echo off && call %userprofile%\.vim\wincmds\alias_dotconf.cmd %*

@REM echo off && call %userprofile%\.vim\wincmds\alias_bldbx.cmd %*

@REM echo off && call %userprofile%\.vim\wincmds\alias_nbu.cmd %*
@REM echo off && call %userprofile%\.vim\wincmds\alias_postgres.cmd %*
@REM echo off && call %userprofile%\.vim\wincmds\alias_bmr.cmd %*
@REM echo off && call %userprofile%\.vim\wincmds\alias_nbu_special.cmd %*
@REM echo off && call %userprofile%\.vim\scripts\definstallpathsmacro.cmd %*
@REM echo off && call %userprofile%\.vim\wincmds\alias_sf.cmd %*

@REM echo off && call %userprofile%\.vim\wincmds\alias_ps.cmd %*

@IF EXIST %userprofile%\alias.tmp.cmd call %userprofile%\alias.tmp.cmd %*
@IF EXIST %userprofile%\alias.loc.cmd call %userprofile%\alias.loc.cmd %*

@IF "%1" == "QUICK_ACCESS" DOSKEY /MACROFILE=%userprofile%\alias.doskey

@REM @SET PATH=%PATH%;
@REM PATH FOR WGET command on windows
@REM @SET PATH=%PATH%;C:\Program Files (x86)\GnuWin32\bin;

@REM Clear the screen
@REM cls


