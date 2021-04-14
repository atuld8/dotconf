#!/bin/bash
set -x

cd ~
git clone https://github.com/atuld8/dotconf.git .vim
git clone https://github.com/VundleVim/Vundle.vim.git .vim/bundle/Vundle.vim

cd ~
echo source ~/.vim/vimrc >> .vimrc
echo source ~/.vim/gvimrc >> .gvimrc

ln -s ~/.vim/tmux.conf .tmux.conf
ln -s ~/.vim/screenrc .screenrc
ln -s ~/.vim/emacs .emacs

mkdir ~/bin
cp ~/.vim/alias ~/.alias
cp ~/.vim/gitconfig ~/.gitconfig
cp ~/.vim/rootDiskUsage.sh ~/bin
cp ~/.vim/export.var ~/.export.var
cp ~/.vim/export.vrts ~/.export.vrts

source ~/.alias
chmod 700 ~/.alias ~/.vimrc ~/.emacs ~/.vim ~/.ssh ~/.gitconfig ~/.tmux.conf ~/.screenrc ~/.bashrc ~/.export.var ~/.export.vrts ~/.alias.loc ~/.alias.tmp

# for Unix
#echo source ~/.vim/bashrc >>  ~/.bashrc

#for cygwin
echo source ~/.vim/wincmds/bashrc >>  ~/.bashrc
echo SetBasicTrap >> ~/.bashrc

vim -c ":PluginInstall"

rm -fr ~/.vim/bundle/YouCompleteMe
rm -fr ~/.vim/bundle/ultisnips
