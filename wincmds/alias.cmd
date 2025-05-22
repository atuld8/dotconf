@SET ALIAS_FOR_ADV_ON=0
@SET ALIAS_FOR_BLD_ON=0
@SET ALIAS_FOR_NBU_ON=0
@SET ALIAS_FOR_SF_ON=0
@SET ALIAS_FOR_PS_ON=0


@IF EXIST %userprofile%\set.var.cmd call %userprofile%\set.var.cmd %*
@IF EXIST %userprofile%\set.vrts.cmd call %userprofile%\set.vrts.cmd %*

@REM @echo Initializing... This may take some time...
@ECHO off && call %userprofile%\.vim\wincmds\alias_global.cmd %*


@IF %ALIAS_FOR_ADV_ON% NEQ 1 GOTO SKIP_ALIAS_FOR_ADV
@ECHO off && call %userprofile%\.vim\wincmds\alias_dotconf.cmd %*
:SKIP_ALIAS_FOR_ADV

@IF %ALIAS_FOR_BLD_ON% NEQ 1 GOTO SKIP_ALIAS_FOR_BLD
@ECHO off && call %userprofile%\.vim\wincmds\alias_bldbx.cmd %*
:SKIP_ALIAS_FOR_BLD

@IF %ALIAS_FOR_NBU_ON% NEQ 1 GOTO SKIP_ALIAS_FOR_NBU

@ECHO off && call %userprofile%\.vim\wincmds\alias_nbu.cmd %*
@ECHO off && call %userprofile%\.vim\wincmds\alias_postgres.cmd %*
@ECHO off && call %userprofile%\.vim\wincmds\alias_bmr.cmd %*
@ECHO off && call %userprofile%\.vim\wincmds\alias_nbu_special.cmd %*
@ECHO off && call %userprofile%\.vim\scripts\definstallpathsmacro.cmd %*
:SKIP_ALIAS_FOR_NBU

@IF %ALIAS_FOR_SF_ON% NEQ 1 GOTO SKIP_ALIAS_FOR_SF
@ECHO off && call %userprofile%\.vim\wincmds\alias_sf.cmd %*
:SKIP_ALIAS_FOR_SF

@IF %ALIAS_FOR_PS_ON% NEQ 1 GOTO SKIP_ALIAS_FOR_PS
@ECHO off && call %userprofile%\.vim\wincmds\alias_ps.cmd %*
:SKIP_ALIAS_FOR_PS

@IF EXIST %userprofile%\alias.tmp.cmd call %userprofile%\alias.tmp.cmd %*
@IF EXIST %userprofile%\alias.loc.cmd call %userprofile%\alias.loc.cmd %*

@IF "%1" == "QUICK_ACCESS" DOSKEY /MACROFILE=%userprofile%\alias.doskey

@REM @SET PATH=%PATH%;
@REM PATH FOR WGET command on windows
@REM @SET PATH=%PATH%;C:\Program Files (x86)\GnuWin32\bin;

@REM Clear the screen
@REM cls


