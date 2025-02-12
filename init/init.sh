#!/bin/bash
set -x

cd ~
git clone https://github.com/atuld8/dotconf.git .vim
git clone https://github.com/VundleVim/Vundle.vim.git .vim/bundle/Vundle.vim

cd ~
echo source ~/.vim/vimrc >> .vimrc
echo source ~/.vim/gvimrc >> .gvimrc
echo source-file  ~/.vim/tmux.conf >> .tmux.conf
echo source-file  ~/.vim/tmux.conf.mac >> .tmux.conf
#echo source-file  ~/.vim/tmux.conf.cyg_lnx >> .tmux.conf

ln -s ~/.vim/screenrc .screenrc
ln -s ~/.vim/emacs .emacs

mkdir ~/bin
cp ~/.vim/alias ~/.alias
cp ~/.vim/gitconfig ~/.gitconfig
cp ~/.vim/rootDiskUsage.sh ~/bin
cp ~/.vim/export.var ~/.export.var
cp ~/.vim/export.vrts ~/.export.vrts
cp ~/.vim/psqlrc ~/.psqlrc

source ~/.alias
chmod 700 ~/.alias ~/.vimrc ~/.emacs ~/.vim ~/.ssh ~/.gitconfig ~/.tmux.conf ~/.screenrc ~/.bashrc ~/.export.var ~/.export.vrts ~/.alias.loc ~/.alias.tmp

echo source ~/.vim/bashrc >>  ~/.bashrc
#echo "echo source ~/.vim/wincmds/bashrc >>  ~/.bashrc for cygwin "
echo SetBasicTrap >> ~/.bashrc

vim -c ":PluginInstall"

rm -fr ~/.vim/bundle/YouCompleteMe
rm -fr ~/.vim/bundle/ultisnips
