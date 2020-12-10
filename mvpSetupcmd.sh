cd ~

git clone https://github.com/atuld8/dotconf.git .vim
git clone https://github.com/VundleVim/Vundle.vim.git .vim/bundle/Vundle.vim

cd ~
echo source ~/.vim/vimrc >> .vimrc
echo source ~/.vim/gvimrc >> .gvimrc

cd ~
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
echo "echo source ~/.vim/bashrc >>  ~/.bashrc for Unix "
echo "echo source ~/.vim/wincmds/bashrc >>  ~/.bashrc for cygwin "
echo "echo SetShortTrap >> ~/.bashrc"

vim -c ":PluginInstall"

rm -fr ~/.vim/bundle/YouCompleteMe
rm -fr ~/.vim/bundle/ultisnips
