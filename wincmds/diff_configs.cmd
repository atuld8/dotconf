@REM the nerdtree is disabled default, hence below line is not required.
@REM START cmd /c gvim --servername wincmd.diff +"call F_toggle_nerdtree_settings()" +"vsp %USERPROFILE%\.vim\wincmds\gitconfig" +"windo diffthis" %USERPROFILE%\.gitconfig

START cmd /c gvim --servername wincmd.diff +"vsp %USERPROFILE%\.vim\wincmds\gitconfig" +"windo diffthis" %USERPROFILE%\.gitconfig
timeout /T -1
START cmd /c gvim --servername wincmd.diff --remote-tab +"vsp %USERPROFILE%\.vim\vimrc| windo diffthis" %USERPROFILE%\_vimrc
timeout /NOBREAK 2
START cmd /c gvim --servername wincmd.diff --remote-tab +"vsp %USERPROFILE%\.vim\emacs | windo diffthis" %APPDATA%\.emacs
timeout /NOBREAK 2
START cmd /c gvim --servername wincmd.diff --remote-tab +"vsp %USERPROFILE%\.vim\emacs-keybindings.el | windo diffthis" %APPDATA%\.vim\emacs-keybindings.el
timeout /NOBREAK 2
START cmd /c gvim --servername wincmd.diff --remote-tab +"vsp %USERPROFILE%\.vim\wincmds\alias.cmd | windo diffthis" %userprofile%\alias.cmd

copy /y %USERPROFILE%\.vim\*.el %APPDATA%\.vim
gvim --servername wincmd.diff --remote-tab  PluginInstall
