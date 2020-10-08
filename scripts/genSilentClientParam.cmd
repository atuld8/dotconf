@FOR /F "tokens=1,2,* " %%a in ('reg query HKEY_LOCAL_MACHINE\SOFTWARE\Veritas\NetBackup\CurrentVersion\config 2^>NUL^|findstr "EMMSERVER"') DO @echo SET PRIMARYSERVER=%%c
@FOR /F "tokens=1,2,3,4" %%a in ('nbcertcmd.exe -displayCACertDetail 2^>NUL^|findstr /C:"SHA-1 Fingerprint"') DO @echo SET CA_CERTIFICATE_FINGERPRINT=%%d
@FOR /F "tokens=1,2,3,4" %%a in ('nbcertcmd.exe -displayToken -name clientInstall 2^>NUL^|findstr /C:"Token Value"') DO @echo SET AUTHORIZATION_TOKEN=%%d
@ECHO.
@ECHO.
@ECHO.
@ECHO.
@FOR /F "tokens=1,2,* " %%a in ('reg query HKEY_LOCAL_MACHINE\SOFTWARE\Veritas\NetBackup\CurrentVersion\config 2^>NUL^|findstr "EMMSERVER"') DO @echo SET PRIMARYSERVER=%%c
@FOR /F "tokens=1,2,3,4" %%a in ('nbcertcmd.exe -displayCACertDetail 2^>NUL^|findstr /C:"SHA-256 Fingerprint"') DO @echo SET CA_CERTIFICATE_FINGERPRINT=%%d
@FOR /F "tokens=1,2,3,4" %%a in ('nbcertcmd.exe -displayToken -name clientInstall 2^>NUL^|findstr /C:"Token Value"') DO @echo SET AUTHORIZATION_TOKEN=%%d
@ECHO.
@ECHO.
