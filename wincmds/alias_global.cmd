@ECHO off

@SET EXTRA_PROMPT_DATA=$S
@SET PROMPT=$C$D$S$T$F$S$M[%COMPUTERNAME%]$S$P$S%EXTRA_PROMPT_DATA%$_$+$G$G$S

@IF NOT DEFINED GIT_USER @SET GIT_USER=
@IF NOT DEFINED GIT_SERVER @SET GIT_SERVER=

@SET DOSKEY_ALL_MACROS=DOSKEY /MACROS

@IF "%1" == "QUICK_ACCESS" GOTO QA_ALIAS_GLOBAL

@DOSKEY alias=%DOSKEY_ALL_MACROS% $*
@DOSKEY a=%DOSKEY_ALL_MACROS% $*
@DOSKEY a.list.col=(@FOR /F "tokens=1,* delims==" %%a in ('@DOSKEY /MACROS') DO @ECHO^|@SET /P="%%a      " )
@DOSKEY a.list=(@FOR /F "tokens=1,* delims==" %%a in ('@DOSKEY /MACROS') DO @ECHO %%a )
@DOSKEY f.a=%DOSKEY_ALL_MACROS% ^| findstr /I $*
@DOSKEY f.a1=%DOSKEY_ALL_MACROS% ^| findstr /I $1
@DOSKEY f.ao=%DOSKEY_ALL_MACROS% ^| findstr /I /B $1=
@DOSKEY f.af=findstr /I $* "%userprofile%"\.vim\wincmds\alias* "%userprofile%"\alias.cmd
@DOSKEY f.afa=findstr /I $* "%userprofile%"\.vim\wincmds\alias* "%userprofile%"\alias* "%userprofile%"\.vim\alias*
@DOSKEY f.a1fa=findstr /I /B $*= "%userprofile%"\.vim\wincmds\alias* "%userprofile%"\alias* "%userprofile%"\.vim\alias*
@DOSKEY a.print=@FOR /F "tokens=1,* delims==" %%a in ('DOSKEY /MACROS ^^^| findstr /I $1') do @FOR /F "tokens=1,*" %%x in ("$*") do @ECHO cmd:%%b args:%%y
@DOSKEY f.g=git alias ^| findstr /I $*
@DOSKEY history.find=Doskey /history ^| findstr /I $*
@DOSKEY history=Doskey /history $*
@DOSKEY pushd=%~dp0pushd.cmd $*
@DOSKEY popd=%~dp0pushd.cmd popd
@DOSKEY paths=cmd /v:on /c "for %%p in ("!path:;=" "!") do @echo %%~p | findstr /V /C:"ECHO is on""
@DOSKEY v=gvim $*
@DOSKEY v++=gvim -c "set tags+=tags" -c "cs add cscope.out" $*
@DOSKEY clr=cls^&dir /P /D $*
@DOSKEY ll=dir $*
@DOSKEY l1=dir /b $*
@DOSKEY la=dir /A /b $*
@DOSKEY l=dir /A /D /N $*
@DOSKEY lr=dir /A /S /B $*
@DOSKEY ld=dir /A:D /B $*

@DOSKEY macros=%DOSKEY_ALL_MACROS% $*
@DOSKEY d=gvim -d $*
@DOSKEY c=cls
@DOSKEY a.cd=%DOSKEY_ALL_MACROS% ^| findstr "cd\..*=" $*
@DOSKEY a.x=%DOSKEY_ALL_MACROS% ^| findstr "\<x\..*=" $*
@DOSKEY a.cat=%DOSKEY_ALL_MACROS% ^| findstr "cat\..*=" $*
@DOSKEY a.cp=%DOSKEY_ALL_MACROS% ^| findstr "cp\..*=" $*
@DOSKEY a.edt=%DOSKEY_ALL_MACROS%  ^| findstr "\<e\..*=" ^| findstr /V "\.e\..*=" $*
@DOSKEY a.edt.all=%DOSKEY_ALL_MACROS%  ^| findstr "e\..*="  $*
@DOSKEY a.als=%DOSKEY_ALL_MACROS%  ^| findstr "^\a\..*=" ^| findstr /V "\.a\..*="  $*
@DOSKEY a.a.all=%DOSKEY_ALL_MACROS%  ^| findstr "a\..*=" $*
@DOSKEY a.dff=%DOSKEY_ALL_MACROS%  ^| findstr "\<d\..*=" $*
@DOSKEY a.find=%DOSKEY_ALL_MACROS% ^| findstr "$1*=" $2 $3 $4 $5
@DOSKEY a.git=%DOSKEY_ALL_MACROS%  ^| findstr "\<g\..*=" $*
@DOSKEY a.get=%DOSKEY_ALL_MACROS% ^| findstr "get\..*=" $*
@DOSKEY a.hlp=%DOSKEY_ALL_MACROS%  ^| findstr "\<h\..*=" $*
@DOSKEY a.loc=%DOSKEY_ALL_MACROS%  ^| findstr "^.*\.l\..*=" $*
@DOSKEY a.misc=%DOSKEY_ALL_MACROS%  ^| findstr "\<m\..*=" $*
@DOSKEY a.othr=%DOSKEY_ALL_MACROS%  ^| findstr "\<o\..*=" $*
@DOSKEY a.path=%DOSKEY_ALL_MACROS%  ^| findstr "\<p\..*=" $*
@DOSKEY a.pd=%DOSKEY_ALL_MACROS% ^| findstr "pd\..*=" $*
@DOSKEY a.qk=%DOSKEY_ALL_MACROS%  ^| findstr "\<q\..*=" $*
@DOSKEY a.reg=%DOSKEY_ALL_MACROS%  ^| findstr "\<r\..*=" $*
@DOSKEY a.run=%DOSKEY_ALL_MACROS%  ^| findstr "\<run\..*=" $*
@DOSKEY a.set=%DOSKEY_ALL_MACROS%  ^| findstr "\<set\..*=" $*
@DOSKEY a.tmp=%DOSKEY_ALL_MACROS%  ^| findstr "\<t\..*=" $*
@DOSKEY a.wmic=%DOSKEY_ALL_MACROS% ^| findstr "wmic\..*=" $*
@DOSKEY a..=%DOSKEY_ALL_MACROS% ^| findstr "^.*\..*\..*=" ^| findstr /v "\.\.\*=" $*
@DOSKEY a.=%DOSKEY_ALL_MACROS%  ^| findstr "\<\..*=" ^| findstr /v ".\.\..*=" $*
@DOSKEY a.@=%DOSKEY_ALL_MACROS%  ^| findstr "^@.*=" $*
@DOSKEY a.xxl=%DOSKEY_ALL_MACROS%  ^| findstr /R "^[a-z]*[a-z]="

@DOSKEY @vim=%~dp0cd.cmd %~dp0/.. ^&^& $* ^& %~dp0cd.cmd -
@DOSKEY @home=%~dp0cd.cmd %userprofile% ^&^& $* ^& %~dp0cd.cmd -

@DOSKEY x.vimpp=gvim -c "args Build TODO" -c "args **/*.pm" -c "args *.pl" $*
@DOSKEY x.setextpmtpdata=FOR /F "tokens=2" %%i in ('git branch ^^^| findstr *') do @SET EXTRA_PROMPT_DATA=(%%i)
@DOSKEY x.vimpull=%~dp0cd.cmd %~dp0/.. ^&^& %~dp0g.cmd pull ^&^& %~dp0cd.cmd -
@DOSKEY x.watch=%~dp0watch.cmd $*
@DOSKEY x.time=%~dp0alias_func.cmd EXECUTION_TIME $*
@DOSKEY x.wget..ln.d=wget -r -R "index.html*" -H -nc -np -nH --no-check-certificate --cut-dirs $2 $1
@DOSKEY x.wget..ln.d.depth=wget -r -R "index.html*" -H -nc -np -nH --no-check-certificate -l $3 --cut-dirs $2 $1
@DOSKEY x.vimpluginst=gvim +PluginInstall +qall
@DOSKEY x.vimplugupd=gvim +PluginUpdate +qall
@DOSKEY x.dir.links=dir /AL /S $*
@DOSKEY x.genctags=ctags -R -a -f tags --c++-kinds=+p --fields=+iaS --extra=+q .
@DOSKEY x.gencscopeStp1=dir /s /b *.c 2^>NUL ^> cscope.files ^^^& dir /s /b *.cpp 2^>NUL ^>^> cscope.files ^^^& dir /s /b *.h 2^>NUL ^>^> cscope.files ^^^& dir /s /b *.hpp 2^>NUL ^>^> cscope.files ^^^& dir /s /b *.java 2^>NUL ^>^> cscope.files ^^^& dir /s /b *.py >NUL ^>^> cscope.files
@DOSKEY x.gencscopeStp2=cscope -q -R -b -v -C -i cscope.files -f cscope.out
@DOSKEY x.gendoskey=copy /y %userprofile%\alias.doskey %userprofile%\alias.doskey.bkp ^& doskey /macros ^> %userprofile%\alias.doskey
@DOSKEY x.reconn=for /f "tokens=2,3" %%a in ('net use ^^^| findstr "^Disconnected ^Unavailable" ^^^| findstr " [A-Z]: "') do net use %%a %%b /PERSISTENT:YES

@DOSKEY d.winc=%~dp0diff_configs.cmd

@DOSKEY e=%%CFG_EDITOR%% $*
@DOSKEY e.ag=%%CFG_EDITOR%% %~dpnx0
@DOSKEY e.l.a=%%CFG_EDITOR%% "%userprofile%\alias.cmd"
@DOSKEY e.l.al=%%CFG_EDITOR%% "%userprofile%\alias.loc.cmd"
@DOSKEY e.l.at=%%CFG_EDITOR%% "%userprofile%\alias.tmp.cmd"
@DOSKEY e.l.adk=%%CFG_EDITOR%% "%userprofile%\alias.doskey"
@DOSKEY e.l.gc=%%CFG_EDITOR%% "%userprofile%\.gitconfig"
@DOSKEY e.l.vimrc=%%CFG_EDITOR%% "%userprofile%\_vimrc"
@DOSKEY e.hosts=%%CFG_EDITOR%% %SystemRoot%\System32\drivers\etc\hosts
@DOSKEY e.rme=%%CFG_EDITOR%% %~dp0..\README.md
@DOSKEY e.scratch=%%CFG_EDITOR%% "%userprofile%\scratch.txt"
@DOSKEY e.key=%%CFG_EDITOR%% "%userprofile%\keyfile.txt"
@DOSKEY e.enc=gvim --cmd "set key=%%VIMPASS%%" $*
@DOSKEY e.tmp..x=%%CFG_EDITOR%% "%%temp%%\tmp$*.txt"
@DOSKEY e.si=%%CFG_EDITOR%% %SystemDrive%\setupinfo.txt $*

@DOSKEY cat.key=type "%userprofile%\keyfile.txt" $*
@DOSKEY cat.rme=type %~dp0..\README.md $*
@DOSKEY cat.hosts=type %SystemRoot%\System32\drivers\etc\hosts $*

@DOSKEY g=%~dp0g.cmd $*
@DOSKEY cd=%~dp0cd.cmd $*
@DOSKEY cdls=%~dp0cd.cmd $* ^&^& dir $*
@DOSKEY mcd=mkdir $* ^&^& cd /d $*

@REM @DOSKEY cd.sample=%~dp0cd.cmd "sample folder with space"\subfolder $*
@DOSKEY cd.up=%~dp0cd.cmd "%userprofile%"\$*
@DOSKEY cd.drpbx=%~dp0cd.cmd "%userprofile%"\Dropbox\$*
@DOSKEY cd.desk=%~dp0cd.cmd "%userprofile%"\Desktop\$*
@DOSKEY cd.down=%~dp0cd.cmd "%userprofile%"\Downloads\$*
@DOSKEY cd.pf=%~dp0cd.cmd "%ProgramFiles%"\$*
@DOSKEY cd.pfx86=%~dp0cd.cmd "%ProgramFiles(x86)%"\$*
@DOSKEY cd.pd=%~dp0cd.cmd "%ProgramData%"\$*
@DOSKEY cd.win=%~dp0cd.cmd "%WINDIR%"\$*
@DOSKEY cd.sys32=%~dp0cd.cmd "%WINDIR%"\system32\$*
@DOSKEY cd.wow64=%~dp0cd.cmd "%WINDIR%"\syswow64\$*
@DOSKEY cd.vim=%~dp0cd.cmd %~dp0\..\$*
@DOSKEY pd.vim=%~dp0pushd.cmd %~dp0\..\$*
@DOSKEY cd.temp=%~dp0cd.cmd %%temp%%
@DOSKEY cd.tmp=%~dp0cd.cmd %SystemDrive%\temp
@DOSKEY cd.wn= %~dp0cd.cmd "%userprofile%"\Dropbox\Worknotes\$*
@DOSKEY cd.data=IF EXIST "%userprofile%\data\$*" ( %~dp0cd.cmd %userprofile%\data\$* ) ELSE ( mkdir "%userprofile%\data\$*" ^& %~dp0cd.cmd %userprofile%\data\$* 2^> NUL )
@DOSKEY cd.sb.stage=IF EXIST "%userprofile%\stage\$*" ( %~dp0cd.cmd %userprofile%\stage\$* ) ELSE ( mkdir "%userprofile%\stage\$*" ^& %~dp0cd.cmd %userprofile%\stage\$* 2^> NUL )

@DOSKEY cd..1=%~dp0cd.cmd .. $*
@DOSKEY cd..2=%~dp0cd.cmd .. 2 $*
@DOSKEY cd..3=%~dp0cd.cmd .. 3 $*
@DOSKEY cd..4=%~dp0cd.cmd .. 4 $*
@DOSKEY cd..5=%~dp0cd.cmd .. 5 $*

@DOSKEY ..=%~dp0cd.cmd .. $*
@DOSKEY ...=%~dp0cd.cmd .. 2 $*
@DOSKEY ....=%~dp0cd.cmd .. 3 $*
@DOSKEY .....=%~dp0cd.cmd .. 4 $*

@DOSKEY cd.gbase=@FOR /f %%d IN ('git rev-parse --show-toplevel') DO @ECHO OFF ^& %~dp0cd.cmd %%d ^& @ECHO ON


@DOSKEY g.alias=%%GIT_CMD_USED%% config --list ^| findstr "alias" $*
@DOSKEY g.brmrgd=if $1. equ . ( %%GIT_CMD_USED%% branch --merged origin/master   ^| findstr /r /v /c:"[* ]*master" ) else ( %%GIT_CMD_USED%% branch --merged origin/$1   ^| findstr /r /v /c:"[* ]*$1" )
@DOSKEY g.drop=%%GIT_CMD_USED%% stash ^& %%GIT_CMD_USED%% stash drop
@DOSKEY g.syncrb=%%GIT_CMD_USED%% remote -v update ^& %%GIT_CMD_USED%% status -uno $*
@DOSKEY g.syncmb=%%GIT_CMD_USED%% remote -v update ^& if $1. equ . ( %%GIT_CMD_USED%% log HEAD..origin/master --oneline $* ) else ( %%GIT_CMD_USED%% log HEAD..origin/$1 --oneline $* )
@DOSKEY g.brrmtlink=git ls-remote --head ^> %temp%\ls-remote.output ^&^& @ECHO OFF ^&^& @FOR /f "tokens=1,2" %%a in ('git branch') DO  @IF "%%a" == "*" ( findstr /c:"refs/heads/%%b" %temp%\ls-remote.output ^| findstr /v /r "%%b." ) ELSE ( findstr /c:"refs/heads/%%a" %temp%\ls-remote.output ^| findstr /v /r "%%a." ) ^&^& @ECHO ON
@DOSKEY g.brcurrmtlink=@FOR /f "tokens=1,2" %%a in ('git branch') DO  @IF "%%a" == "*"  git  ls-remote --head ^| findstr /c:"refs/heads/%%b" ^| findstr /v /r "%%b."
@DOSKEY g.et=@FOR /F "tokens=1,* delims=t" %%a in ('git br ^^^| findstr "*"') do @ECHO %%b^| clip
@DOSKEY g.gh.user.email=git config --local user.email "atuld8@gmail.com"
@DOSKEY g.gh.user.name=git config  --local user.name "atuld8"

@DOSKEY h.doc=vim --cmd "set key=%%VIMPASS%%" -c ":let g:nerdtreefindexec=1" -c ":NERDTree" %~dp0..\doc\*.txt
@DOSKEY h.termhelp=vim --cmd "set key=%%VIMPASS%%" %~dp0\..\doc\Bash.KB.shrtcuts.txt
@DOSKEY h.cpl=dir /b /o %WINDIR%\system32\*.cpl %WINDIR%\SysWOW64\*.cpl $*
@DOSKEY h.msc=dir /b /o %WINDIR%\system32\*.msc %WINDIR%\SysWOW64\*.msc $*


@REM MISC COMMANDS
@DOSKEY .cyg=%%CYGPATH%%\bin\mintty.exe -i /Cygwin-Terminal.ico -  $*
@DOSKEY .bash=cmd /c "set PATH=%%CYGPATH%%\bin;%%PATH%%&& bash $*"
@DOSKEY .cygbash=cmd /c "set PATH=%%CYGPATH%%\bin;%%PATH%%&& bash -l $*"
@DOSKEY .rc=echo %%ERRORLEVEL%% $*
@DOSKEY .xp=%SystemRoot%\explorer.exe $*
@DOSKEY .shell=%SystemRoot%\explorer.exe shell:$*
@DOSKEY .chrome=IF EXIST "%SYSTEMDRIVE%\Program Files (x86)\Google\Chrome\Application\chrome.exe" ("%SYSTEMDRIVE%\Program Files (x86)\Google\Chrome\Application\chrome.exe" $* ) ELSE ("%SYSTEMDRIVE%\Program Files\Google\Chrome\Application\chrome.exe" $*)
@DOSKEY .firefox="%SYSTEMDRIVE%\Program Files (x86)\Mozilla Firefox\firefox.exe" $*
@DOSKEY .py=python $*
@DOSKEY .orca="%SYSTEMDRIVE%\ProgramData\Microsoft\Windows\Start Menu\Programs\orca.lnk" $*
@DOSKEY .ssh=IF DEFINED SSH_EXTRA_ARG (ssh -X -Y -t -o  StrictHostKeyChecking=no  -o "TCPKeepAlive=yes" -o "ServerAliveInterval=90" -o "ServerAliveCountMax=10" -o "ForwardX11=yes" %%SSH_EXTRA_ARG%% $* ) ELSE (ssh -X -Y -t -o  StrictHostKeyChecking=no  -o "TCPKeepAlive=yes" -o "ServerAliveInterval=90" -o "ServerAliveCountMax=10" -o "ForwardX11=yes" $* )
@DOSKEY .noclink=start cmd /c $*
@DOSKEY .clink="%ProgramFiles(x86)%\clink\0.4.9\clink.bat" inject $*
@DOSKEY .mini=start "cmd" /I /D %userprofile% cmd "/k mini.cmd"
@DOSKEY .pushd=%~dp0alias_func.cmd CD_TO_PUSHD_MACROS $*
@DOSKEY .fs=findstr /I $*
@DOSKEY .np++="%SYSTEMDRIVE%\Program Files (x86)\Notepad++\notepad++.exe" $*
@DOSKEY .tp="%SYSTEMDRIVE%\Program Files (x86)\TextPad 4\TextPad.exe" $*
@DOSKEY .np=notepad $*
@DOSKEY .wmrg="%SYSTEMDRIVE%\Program Files (x86)\\WinMerge\WinMergeU.exe" $*
@DOSKEY .mv2org=rename $* $*.org
@DOSKEY .mv4org=rename $*.org $*
@DOSKEY .7z="%SYSTEMDRIVE%\Program Files\7-Zip\7z.exe" $*
@DOSKEY .st3="%SYSTEMDRIVE%\Program Files\Sublime Text 3\sublime_text.exe" $*
@DOSKEY .ff=FORFILES /S /C "cmd /c echo @path" $*
@DOSKEY .mbxtrm.cwd="%SYSTEMDRIVE%\Program Files (x86)\Mobatek\MobaXterm\MobaXterm.exe" -openfolder "%%cd%%" $*
@DOSKEY .mbxtrm.tb="%SYSTEMDRIVE%\Program Files (x86)\Mobatek\MobaXterm\MobaXterm.exe" -newtab $*
@DOSKEY .mbxtrm.cmd="%SYSTEMDRIVE%\Program Files (x86)\Mobatek\MobaXterm\MobaXterm.exe" -bookmark Cmd $*
@DOSKEY .mbxtrm="%SYSTEMDRIVE%\Program Files (x86)\Mobatek\MobaXterm\MobaXterm.exe" $*
@DOSKEY .hlp=$* 2^>^&1^| vim -R -
@DOSKEY .as="C:\Program Files\Android\Android Studio\bin\studio64.exe"
@DOSKEY .vsc="C:\Users\atul.das1\AppData\Local\Programs\Microsoft VS Code\bin\code.cmd"
@DOSKEY .mr=more /E /C /T4 $*

@DOSKEY cp.vp=echo^|set /p=%%VIMPASS%%^|clip
@DOSKEY cp.accTkn=echo^|set /p=%%ACCESS_TOKEN%%^|clip
@DOSKEY cp.cwd=echo^|set /p=%%CD%%$*^|clip
@DOSKEY cp.un=echo^|set /p=%%USERNAME%%$*^|clip
@DOSKEY cp.hn=echo^|set /p=%%COMPUTERNAME%%$*^|clip
@DOSKEY cp.unc=echo^|set /p=\\%%COMPUTERNAME%%\%%CD::=$%%^|clip
@DOSKEY cp.unc.mnt=@FOR /f "tokens=1,2,*" %%f in ('net use %%CD:~0,2%% ^^^| findstr "Remote Name"') do @ECHO %%h\%%CD:~3%%^|CLIP
@DOSKEY cp.gbr=git rev-parse --abbrev-ref HEAD^|clip
@DOSKEY cp.gbret=@FOR /f "tokens=2 delims=et" %%a in ('git rev-parse --abbrev-ref HEAD') do @echo %%a^|clip
@DOSKEY cp.nb.env.unix=clip^<%~dp0..\scripts\.nb.unix.env.sh
@DOSKEY cp.nb.env.win=clip^<%~dp0..\scripts\.nb.win.env.cmd
@DOSKEY cp.es=%~dp0..\scripts\echo.line.sep.cmd $*^|clip
@DOSKEY cp.tmp..x=echo^|set /p="%%temp%%\tmp$*.txt"^|clip
@DOSKEY cp.clear=@echo^|set /p=^|clip
@DOSKEY cp.alias=@doskey /macros^|findstr "\<"$*"\>"^|clip

@REM https://autohotkey.com/docs/misc/CLSID-List.htm
@DOSKEY o.comp=%%OPEN_CMD%% ::{20d04fe0-3aea-1069-a2d8-08002b30309d}$*
@DOSKEY o.admT=%%OPEN_CMD%% ::{d20ea4e1-3957-11d2-a40b-0c5020524153}$*
@DOSKEY o.cntP=%%OPEN_CMD%% ::{21ec2020-3aea-1069-a2dd-08002b30309d}$*
@DOSKEY o.rclB=%%OPEN_CMD%% ::{645ff040-5081-101b-9f08-00aa002f954e}$*
@DOSKEY o.cntP=%%OPEN_CMD%% ::{21ec2020-3aea-1069-a2dd-08002b30309d}$*
@DOSKEY o.tmpI=%%OPEN_CMD%% ::{7bd29e00-76c1-11cf-9dd0-00a0c9034933}$*

@REM SET NEW VALUE TO VARIABLE
@DOSKEY set.gcmd=SET GIT_CMD_USED=%~dp0g.cmd
@DOSKEY set.git=SET GIT_CMD_USED=git
@DOSKEY set.gst.basic=SET PROMPT=[%COMPUTERNAME%]$S$P$SCmd$+$$$ ^& SET GIT_STATUS_LEVEL=-1
@DOSKEY set.gst..n=SET GIT_STATUS_LEVEL=$1
@DOSKEY get.gst=@ECHO %%GIT_STATUS_LEVEL%%
@DOSKEY set.gbase1U=@FOR /f %%d IN ('git rev-parse --show-toplevel') DO @SET "gbase=%%d"
@DOSKEY set.gbase2W=@SET gbase=%%gbase:/=\%%
@DOSKEY set.es=SET es=echo. ^^^& echo -------------------------------------- -------------------------------------- -------------------------------------- ^^^& echo.
@DOSKEY set.e..b=SET CFG_EDITOR=$*
@DOSKEY set.e.np++=SET CFG_EDITOR="C:\Program Files (x86)\Notepad++\notepad++.exe"
@DOSKEY set.e.tp=SET CFG_EDITOR="C:\Program Files (x86)\TextPad 4\TextPad.exe"
@DOSKEY get.e=@ECHO %%CFG_EDITOR%%
@DOSKEY set.o.st=SET OPEN_CMD=start
@DOSKEY set.o.xp=SET OPEN_CMD=explorer
@DOSKEY get.o=@ECHO %%OPEN_CMD%%

@DOSKEY set.p.gitunix=SET PATH=%ProgramFiles%\Git\usr\bin;%%PATH%%
@DOSKEY set.p.cygappnd=SET PATH=%%PATH%%;%%CYGPATH%%\bin
@DOSKEY set.p.perl=SET PATH=%%PERLPATH%%\bin;%%PATH%%
@DOSKEY set.p.java=SET PATH=%%JAVA_HOME%%\bin;%%PATH%%
@DOSKEY set.p.dcbin=SET PATH=%~dp0bin;%~dp0..\scripts;%%PATH%%
@DOSKEY set.p.py=SET PATH=%%LOCALAPPDATA%%\Programs\Python\Python310\;%%PATH%%

@DOSKEY set.p.list=for /f "tokens=* delims=;" %%l in ('set /p ".=%path:"=%"^^^<NUL') do @SET pathlist=%%~l ^& cmd /v:on /c "for %%p in ("!pathlist:;=" "!") do @IF NOT ""%%~p"" == """" ( @IF NOT ""%%~p"" == "" "" @echo %%~p)"
@DOSKEY set.p.list=cmd /v:on /c "SET PATHWithoutDQ=%%PATH:""=%% & for %%p in ("!PATHWithoutDQ:;=" "!") do @IF NOT ""%%~p"" == "" "" (@IF NOT ""%%~p"" == """" @echo %%~p| findstr /V /C:"ECHO is on")"
@DOSKEY set.p.listdq=cmd /v:on /c "SET PATHWithoutDQ=%%PATH:""=%% & for %%p in ("!PATHWithoutDQ:;=" "!") do @IF NOT ""%%~p"" == "" "" (@IF NOT ""%%~p"" == ""  "" (@IF NOT ""%%~p"" == """" @echo "%%~p"))"

@DOSKEY set.pmpt.cmdsep=SET MY_PROMPT_SHOULD_BE_SIMPLE=9^&SET PROMPT=--------- --------- --------- --------- --------- --------- --------- ---------$_Cmd$$$$$S

@DOSKEY set.a=@echo off ^&^& @call %userprofile%\alias.cmd $* ^& @echo on
@DOSKEY set.aqa=@echo off ^&^& @call %userprofile%\alias.cmd QUICK_ACCESS $* ^& @echo on
@DOSKEY set.a.dc=@echo off ^&^& @call %~dp0alias_dotconf.cmd $* ^& @echo on
@DOSKEY set.a.doskey=@DOSKEY /MACROFILE=%userprofile%\alias.doskey
@DOSKEY set.a.odd=@echo off ^&^& @call %~dp0alias_odd.cmd $* ^& @echo on
@DOSKEY set.a.oc=@echo off ^&^& @call %~dp0alias_oc.cmd $* ^& @echo on
@DOSKEY set.a.loc=@echo off ^&^& @call %userprofile%\alias.loc.cmd $* ^& @echo on
@DOSKEY set.a.nb=@echo off ^&^& @call %~dp0alias_nbu.cmd $* ^& @echo on
@DOSKEY set.a.bmr=@echo off ^&^& @call %~dp0alias_bmr.cmd $* ^& @echo on
@DOSKEY set.a.nbsp=@echo off ^&^& @call %~dp0alias_nbu_special.cmd $* ^& @echo on
@DOSKEY set.a.sf=@echo off ^&^& @call %~dp0alias_sf.cmd $* ^& @echo on
@DOSKEY set.a.ps=@echo off ^&^& @call %~dp0alias_ps.cmd $* ^& @echo on
@DOSKEY set.a.bld=@echo off ^&^& @call %~dp0alias_bldbx.cmd $* ^& @echo on
@DOSKEY set.a.gbl=@echo off ^&^& @call %~dp0alias_global.cmd $* ^& @echo on
@DOSKEY set.a.inst=@echo off ^&^& @call %~dp0..\scripts\definstallpathsmacro.cmd $* ^& @echo on
@DOSKEY set.a.tmp=@echo off ^&^& @call %userprofile%\alias.tmp.cmd $* ^& @echo on
@DOSKEY set.a.nbsdtest=@echo off ^&^& @call %~dp0alias_nbsd_test.cmd $* ^& @echo on

@REM REGISTRY KEY ACCESS
@DOSKEY r.lk.svc=REG ADD HKCU\Software\Microsoft\Windows\CurrentVersion\Applets\Regedit /v LastKey /t REG_SZ /d Computer\HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\services /f ^& regedit
@DOSKEY r.lk.any=REG ADD HKCU\Software\Microsoft\Windows\CurrentVersion\Applets\Regedit /v LastKey /t REG_SZ /d $* /f ^& regedit
@DOSKEY r.lk.msi=REG ADD HKCU\Software\Microsoft\Windows\CurrentVersion\Applets\Regedit /v LastKey /t REG_SZ /d HKEY_LOCAL_MACHINE\SOFTWARE\Policies\Microsoft\Windows\Installer /f ^& regedit
@DOSKEY r.msi.setlog=REG ADD HKEY_LOCAL_MACHINE\SOFTWARE\Policies\Microsoft\Windows\Installer /v Logging /t REG_SZ /d voicewarmupx /f ^&^& REG ADD HKEY_LOCAL_MACHINE\SOFTWARE\Policies\Microsoft\Windows\Installer /v Debug /t REG_DWORD /d 7 /f
@DOSKEY r.doskey.addperm=REG ADD "HKCU\Software\Microsoft\Command Processor" /v Autorun /d "doskey /macrofile=\"%userprofile%\alias_perm.doskey\"" /f
@DOSKEY r.doskey.listperm=REG QUERY "HKCU\Software\Microsoft\Command Processor" /v Autorun

@REM WMIC COMMANDS
@DOSKEY wmic.prodlist=wmic product get name, version
@DOSKEY wmic.drives=wmic logicaldisk get Caption, Description, ProviderName
@DOSKEY wmic.drvbrf=wmic logicaldisk list brief
@DOSKEY wmic.help=wmic logicaldisk get /?
@DOSKEY wmic.brf=wmic $* list brief
@DOSKEY wmic.binver.tvar=IF NOT DEFINED TVAR ( @ECHO Pleae define TVAR as filepath ) ELSE ( wmic datafile  where name='%%tvar:\=\\%%' get Name,Version,Manufacturer /format:table )
@DOSKEY wmic.lnkDest.tvar=wmic path win32_shortcutfile where "name='%%tvar:\=\\%%'" get target /value
@DOSKEY wmic.proclist=wmic  PROCESS get Processid,ExecutablePath

@DOSKEY cvdiff=e:\Tools\cvsvimdiff.bat

@REM facing issue with bld box, so commented
@REM IF NOT DEFINED ALREADY_SET_THE_GLOBAL_PATH @SET PATH="C:\Program Files (x86)\Python35";%PATH% && SET ALREADY_SET_THE_GLOBAL_PATH=1
:QA_ALIAS_GLOBAL

@IF NOT DEFINED CFG_EDITOR @SET    CFG_EDITOR=notepad

@SET dt2=..\..
@SET dt3=..\..\..
@SET dt4=..\..\..\..
@SET dt5=..\..\..\..\..
@SET dt6=..\..\..\..\..\..
@SET dt7=..\..\..\..\..\..\..

@SET GIT_CMD_USED=%~dp0g.cmd
@IF NOT DEFINED CYGPATH @SET CYGPATH=C:\cygwin64

@IF NOT DEFINED OPEN_CMD   @SET    OPEN_CMD=explorer

@CALL %~dp0gitbranch.cmd

