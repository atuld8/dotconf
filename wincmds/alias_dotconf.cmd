@IF "%1" == "QUICK_ACCESS" GOTO QA_ALIAS_DOTCONF

@DOSKEY d.vimrc=gvim $* -d "%userprofile%"\_vimrc %~dp0..\vimrc
@DOSKEY d.emacs=gvim $* -d "%userprofile%"\.emacs %~dp0..\emacs
@DOSKEY d.emacsl=gvim $* -d "%appdata%"\.emacs %~dp0..\emacs
@DOSKEY d.gc=gvim $* -d "%userprofile%"\.gitconfig %~dp0\gitconfig
@DOSKEY d.gcw=gvim $* -d "%userprofile%"\.gitconfig %~dp0..\gitconfig %~dp0gitconfig
@DOSKEY d.a=gvim $* -d "%userprofile%"\alias.cmd %~dp0alias.cmd
@DOSKEY d.apd=gvim $* -d "%userprofile%"\alias_perm.doskey %~dp0alias_perm.doskey
@DOSKEY d.awa=gvim -c "vsp %~dp0..\alias" %~dp0alias_global.cmd
@DOSKEY d.awag=gvim -c "vsp %~dp0..\alias" -c "vsp %~dp0..\gitconfig_global" %~dp0alias_global.cmd
@DOSKEY d.bwbsb=gvim -c "vsp %~dp0..\bashrc" -c "vsp %~dp0..\scripts\.bashrc.sh" %~dp0bashrc

@DOSKEY e.af=%%CFG_EDITOR%% %~dp0alias_func.cmd
@DOSKEY e.adc=%%CFG_EDITOR%% %~dp0alias_dotconf.cmd
@DOSKEY e.aod=%%CFG_EDITOR%% %~dp0alias_odd.cmd
@DOSKEY e.ab=%%CFG_EDITOR%% %~dp0alias_bldbx.cmd
@DOSKEY e.an=%%CFG_EDITOR%% %~dp0alias_nbu.cmd
@DOSKEY e.av=%%CFG_EDITOR%% %~dp0alias_vrts.cmd
@DOSKEY e.asf=%%CFG_EDITOR%% %~dp0alias_sf.cmd
@DOSKEY e.a=%%CFG_EDITOR%% %~dp0alias.cmd
@DOSKEY e.ao=%%CFG_EDITOR%% %~dp0..\alias
@DOSKEY e.aog=%%CFG_EDITOR%% %~dp0..\alias.global
@DOSKEY e.aon=%%CFG_EDITOR%% %~dp0..\alias.nbu
@DOSKEY e.gc=%%CFG_EDITOR%% %~dp0gitconfig
@DOSKEY e.gco=%%CFG_EDITOR%% %~dp0..\gitconfig
@DOSKEY e.gcog=%%CFG_EDITOR%% %~dp0..\gitconfig_global
@DOSKEY e.gcg=%%CFG_EDITOR%% %~dp0gitconfig_global
@DOSKEY e.gcmd=%%CFG_EDITOR%% %~dp0g.cmd
@DOSKEY e.gbcmd=%%CFG_EDITOR%% %~dp0gitbranch.cmd
@DOSKEY e.cdcmd=%%CFG_EDITOR%% %~dp0cd.cmd
@DOSKEY e.pdcmd=%%CFG_EDITOR%% %~dp0pushd.cmd
@DOSKEY e.winc=%%CFG_EDITOR%% %~dp0diff_configs.cmd
@DOSKEY e.watch=%%CFG_EDITOR%% %~dp0watch.cmd
@DOSKEY e.cygcmd=%%CFG_EDITOR%% %~dp0cygcmd.cmd


@DOSKEY e.aaa=%%MULTI_CFG_EDITOR%% %~dp0..\alias %~dp0alias.cmd
@DOSKEY e.aag=%%MULTI_CFG_EDITOR%% %~dp0..\alias.global %~dpnx0
@DOSKEY e.aan=%%MULTI_CFG_EDITOR%% %~dp0..\alias.nbu %~dp0alias_nbu.cmd

@DOSKEY set.e.multi.gvim=SET MULTI_CFG_EDITOR=gvim
@DOSKEY set.e.multi.vim=SET MULTI_CFG_EDITOR=vim

@DOSKEY x.vimacp=%~dp0cd.cmd %~dp0/.. ^&^& %%GIT_CMD_USED%% commit -a --reuse-message=HEAD ^&^& %%GIT_CMD_USED%% pull origin ^&^& %%GIT_CMD_USED%% push ^&^& %~dp0cd.cmd -
@DOSKEY x.vimacmp=%~dp0cd.cmd %~dp0/.. ^&^& %%GIT_CMD_USED%% commit -a -m $* ^&^& %%GIT_CMD_USED%% pull origin ^&^& %%GIT_CMD_USED%% push ^&^& %~dp0cd.cmd -
@DOSKEY x.vimdl=%~dp0cd.cmd %~dp0/.. ^&^& %%GIT_CMD_USED%% dl $* ^&^& %~dp0cd.cmd -
@DOSKEY x.bundleupdate=@FOR /f %%d in ('dir /b') do ( start /b cmd /c "echo %%d & cd %%d & git reset --hard & git pull & cd .." )

@DOSKEY p=%temp%\pushd_alias.cmd
@DOSKEY e.pdacmd=%temp%\pushd_alias.cmd

@DOSKEY set.gst.skip=SET GIT_STATUS_LEVEL=0
@DOSKEY set.gst.br=SET GIT_STATUS_LEVEL=1
@DOSKEY set.gst.brst=SET GIT_STATUS_LEVEL=2
@DOSKEY set.gst.full=SET GIT_STATUS_LEVEL=3

@DOSKEY set.e.gvimsvr=SET CFG_EDITOR=gvim --servername CFG_EDITOR --remote-silent
@DOSKEY set.e.gvimsvrtab=SET CFG_EDITOR=gvim --servername CFG_EDITOR --remote-tab-silent
@DOSKEY set.e.gvim=SET CFG_EDITOR=gvim
@DOSKEY set.e.np=SET CFG_EDITOR=notepad
@DOSKEY set.e.cat=SET CFG_EDITOR=type
@DOSKEY set.e.vim=SET CFG_EDITOR=vim
@DOSKEY set.e.emacs=SET CFG_EDITOR=emacs -nw
@DOSKEY set.e.echo=SET CFG_EDITOR=echo

:QA_ALIAS_DOTCONF

@IF NOT DEFINED MULTI_CFG_EDITOR @SET    MULTI_CFG_EDITOR=gvim

