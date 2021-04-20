@call %~dp0alias_vrts.cmd %*

@IF "%1" == "QUICK_ACCESS" GOTO QA_ALIAS_BLDBX

@DOSKEY cmd.epr=cmd /c "%userprofile%\.vim\wincmds\cd.cmd %%ETRACK_CLI_PATH%%\Perl\bin & eprint $*"
@DOSKEY cmd.eprnocmt=cmd /c "%userprofile%\.vim\wincmds\cd.cmd %%ETRACK_CLI_PATH%%\Perl\bin & eprint -v -l -A -f -s -u $*"
@DOSKEY cmd.eprall=cmd /c "%userprofile%\.vim\wincmds\cd.cmd %%ETRACK_CLI_PATH%%\Perl\bin & eprint  -v -l -A -f -c -s -u $*"
@DOSKEY cmd.eq=cmd /c "%userprofile%\.vim\wincmds\cd.cmd %%ETRACK_CLI_PATH%%\Perl\bin & equery $*"
@DOSKEY cmd.eqls=cmd /c "%userprofile%\.vim\wincmds\cd.cmd %%ETRACK_CLI_PATH%%\Perl\bin & equery"
@REM DOSKEY cmd.rmtcmd="ssh.exe" -q -t %RMTCMD_HOST% bash -ic '$*'

@DOSKEY cmd.get-token=python %userprofile%\git-credential-veritas-stash.pex -p https -H %%GIT_SERVER%% -u %%GIT_USER%% get-token
@DOSKEY cmd.renewtoken=cd /d "%userprofile%" ^&^& python3.5 git-credential-veritas-stash.pex -u %%GIT_USER%% -p https -H %%GIT_SERVER%% -l get-token
@DOSKEY cmd.gettoken=@FOR /f "delims=, tokens=3" %%a in (%userprofile%\.stashtokens) do ( @ECHO %%a )
@DOSKEY cmd.gcnb=git clone  -n https://%%GIT_USER%%@%%GIT_SERVER%%/scm/nb/src.git ./src

@DOSKEY e.cmtmsg=%~dp0alias_func.cmd OPEN_COMMIT_MSG_FILE o $*

@DOSKEY g.nbcln.src=%%GIT_CMD_USED%% clone -n https://%%GIT_CREDS%%@%%GIT_SERVER%%/scm/nb/src.git ./src $*
@DOSKEY g.nbcln.src..br=%%GIT_CMD_USED%% clone -n https://%%GIT_CREDS%%@%%GIT_SERVER%%/scm/nb/src.git ./src --branch $*
@DOSKEY g.nbcln.src.sngl..br=%%GIT_CMD_USED%% clone -n https://%%GIT_CREDS%%@%%GIT_SERVER%%/scm/nb/src.git ./src --single-branch --branch $*
@DOSKEY g.nbcln..rp=%%GIT_CMD_USED%% clone -n https://%%GIT_CREDS%%@%%GIT_SERVER%%/scm/nb/$1.git ./$1
@DOSKEY g.nbcln..rp.br=%%GIT_CMD_USED%% clone -n https://%%GIT_CREDS%%@%%GIT_SERVER%%/scm/nb/$1.git ./$1 --branch $2
@DOSKEY g.nbcln.sngl..rp.br=%%GIT_CMD_USED%% clone -n https://%%GIT_CREDS%%@%%GIT_SERVER%%/scm/nb/$1.git ./$1 --single-branch --branch $2
@DOSKEY g.adcln..rp=%%GIT_CMD_USED%% clone -n https://%%GIT_CREDS%%@%%GIT_SERVER%%/scm/~%%GIT_USER%%/$1.git ./$1

@DOSKEY cp.gnburl=echo https://%%GIT_CREDS%%@%%GIT_SERVER%%/scm/nb/$1.git^|clip
@DOSKEY cp.eebver..e.p.s=echo _EEB$1_PET$2_SET$3^|clip

@DOSKEY set.gcred.usr=SET GIT_CREDS=%%GIT_USER%%
@DOSKEY set.gcred.usracctkn=SET GIT_CREDS=%%GIT_USER%%:%%ACCESS_TOKEN%%

@DOSKEY g.addtag=%~dp0alias_func.cmd ADD_EEB_TAG $*
@DOSKEY g.brme=%%GIT_CMD_USED%% ferauth ^| findstr /c:"Atul Das" $*
@DOSKEY g.cmtmsg=%~dp0alias_func.cmd OPEN_COMMIT_MSG_FILE p $*

:QA_ALIAS_BLDBX

@IF NOT DEFINED GIT_CREDS @SET GIT_CREDS=%GIT_USER%


