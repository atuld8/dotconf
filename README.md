# dotconf

http://vimcasts.org/episodes/synchronizing-plugins-with-git-submodules-and-pathogen/

## After clonning perform
```
ln -s ~/.vim/vimrc ~/.vimrc
ln -s ~/.vim/neovimrc ~/.neovimrc
ln -s ~/.vim/tmux.conf ~/.tmux.conf
ln -s ~/.vim/screenrc ~/.screenrc
ln -s ~/.vim/alias ~/.alias.common
ln -s ~/.vim/bashrc ~/.bashrc
ln -s ~/.vim/emacs ~/.emacs
ln -s ~/.vim/nanorc ~/.nanorc
ln -s ~/.vim/tmux ~/.tmux
ln -s ~/.vim/emacs.d/ ~/.emacs.d
ln -s ~/.vim/gitconfig ~/.gitconfig
ln -s ~/.vim/flake8 ~/.flake8
```

## When first time setup the git
```
git init
git config --global user.email atuld8@gmail.com
git config --global user.name  atul
git remote add origin https://github.com/atuld8/dotconf.git
git clone https://github.com/atuld8/dotconf.git
git add README.md
git commit -m "first commit"
git push -u origin master
```

## install plugin as submodule
```
cd ~/.vim
mkdir ~/.vim/bundle
git submodule add http://github.com/tpope/vim-fugitive.git bundle/fugitive
git add .
git commit -m "Install Fugitive.vim bundle as a submodule."
```

## upgrade Vim quickly
```
git clone https://github.com/vim/vim.git
cd vim/src
make

make install
hash -r
```

## Installing your Vim environment on Unix or Cygwin machine
``` Bash
cd ~
git clone https://github.com/atuld8/dotconf.git .vim
git clone https://github.com/VundleVim/Vundle.vim.git .vim/bundle/Vundle.vim
# for p in `egrep "^Plugin" ~/.vim/vundle.vimrc  | sed -e"s/Plugin //" | awk "-F"'" '{print $2;}'`; do git clone  https://github.com/${p}; done

cd ~
echo source ~/.vim/vimrc >> .vimrc
echo source ~/.vim/gvimrc >> .gvimrc
echo source-file  ~/.vim/tmux.conf >> .tmux.conf
ln -s ~/.vim/screenrc .screenrc
ln -s ~/.vim/emacs .emacs

mkdir ~/bin
cp ~/.vim/alias ~/.alias
cp ~/.vim/gitconfig ~/.gitconfig
cp ~/.vim/rootDiskUsage.sh ~/bin
cp ~/.vim/export.var ~/.export.var
cp ~/.vim/export.vrts ~/.export.vrts

source ~/.alias
# chmod 700 ~/.alias ~/.vimrc ~/.emacs ~/.vim ~/.ssh ~/.gitconfig ~/.tmux.conf ~/.screenrc
echo "echo source ~/.vim/bashrc >>  ~/.bashrc for Unix "
echo "echo source ~/.vim/wincmds/bashrc >>  ~/.bashrc for cygwin "
echo "echo SetShortTrap >> ~/.bashrc"
vim -c ":PluginInstall"
rm -fr ~/.vim/bundle/YouCompleteMe
rm -fr ~/.vim/bundle/ultisnips
```

###### Misc
cd ~/.vim
git submodule init
git submodule update

## Installing Vim environment on windows machine
link https://github.com/VundleVim/Vundle.vim/wiki/Vundle-for-Windows
install git
go to %USERPROFILE%
clone github
copy vimrc to _vimrc

#### Steps
``` Batch
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
```

## Upgrading a plugin bundle
At some point in the future, the fugitive plugin might be updated. To fetch the latest changes, go into the fugitive repository, and pull the latest version:
```
cd ~/.vim/bundle/fugitive
git pull origin master
```

## Upgrading all bundled plugins
You can use the foreach command to execute any shell script in from the root of all submodule directories. To update to the latest version of each plugin bundle, run the following:
```
git submodule foreach git pull origin master
```

## MISC HELP
#### pushing your changes to github
```git push -u origin master```

#### facing issue with command-t plugin load
On mac, go to commnd-t plugin directory and run 'rake make' command


#### on Windows, if vundle not working
```
for f in `cat vundle.vimrc | grep "^Plugin" | sed -e"s/Plugin '//" | sed -e"s/'//" | grep -v {`; do git clone  https://github.com/$f ~/dotconf/bundle/`basename $f`; done
```

#### Save github password
```
# Windows
git config credential.helper wincred

# Unix
git config credential.helper cache

# Set the cache to timeout after 1 hour (setting is in seconds)
git config credential.helper 'cache --timeout=999999'
```

#### Setup nvim data
```
mkdir ~/.config/nvim/
mkdir ~/.config/nvim/lua/plugins/
cp ~/.vim/nvim/.config/nvim/init.lua ~/.config/nvim
cp ~/.vim/nvim/.config/nvim/lua/plugins/init.lua ~/.config/nvim/lua/plugins/
```

###### Markdown setting used
* used duble space to add new line charactor
* 3 backquotes to make it code snippet
* Refer # count for formatting
