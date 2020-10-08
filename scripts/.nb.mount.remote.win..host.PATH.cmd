@SETLOCAL enabledelayedexpansion

@IF '%1' == '' goto HELP

@SET REMOTE_HOST=%1
@SET INSTALL_DIR=C$\Program Files\Veritas\

@IF NOT '%2' == '' @SET INSTALL_DIR=%2
   
@ECHO Hostname is !REMOTE_HOST! and Install DIR !INSTALL_DIR! 

@IF NOT '%REMOTE_HOST%' == '-' @PUSHD "\\%REMOTE_HOST%\%INSTALL_DIR%"
@IF '%REMOTE_HOST%' == '-' @CD  /D %INSTALL_DIR%

cmd.exe /k "SET NBU_INST_PATH=%CD%\& SET NBU_CONF_PATH=%CD%\& color 0b"

@IF NOT '%REMOTE_HOST%' == '-' @POPD 

@EXIT /B 0

:HELP
@ECHO Script ComputerName [Install_Dir]
@EXIT /B 1

