set PATH=%PATH%;"c:\Program Files\Git\bin"

cd %USERPROFILE%

git clone https://github.com/atuld8/dotconf.git .vim
git clone https://github.com/VundleVim/Vundle.vim.git .vim/bundle/Vundle.vim

copy /y .vim\gitconfig .gitconfig
copy /y .vim\wincmds\alias_perm.doskey %userprofile%
copy /y .vim\wincmds\alias.loc.cmd %userprofile%
copy /y .vim\wincmds\cygcmd.cmd %windir%\cygcmd.cmd
copy /y .vim\wincmds\acmd.cmd %windir%\acmd.cmd
copy /y .vim\wincmds\qcmd.cmd %windir%\qcmd.cmd
copy /y .vim\wincmds\mini.cmd %windir%\mini.cmd

copy /y .vim\wincmds\set.var.cmd %userprofile%\set.var.cmd
copy /y .vim\wincmds\set.vrts.cmd %userprofile%\set.vrts.cmd

echo source %userprofile%\.vim\vimrc >> %userprofile%\_vimrc
gvim -c ":PluginInstall"
copy /y .vim\emacs %APPDATA%\.emacs
copy /y .vim\emacs-keybindings.el %APPDATA%\.vim\emacs-keybindings.el
mkdir %APPDATA%\.vim
copy /y .vim\*.el %APPDATA%\.vim
copy /y .vim\wincmds\alias.cmd %userprofile%\alias.cmd

rd /q /s %USERPROFILE%\.vim\bundle\ultisnips
rd /q /s %USERPROFILE%\.vim\bundle\YouCompleteMe