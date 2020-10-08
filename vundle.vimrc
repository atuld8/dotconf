set nocompatible              " be iMproved, required
filetype off                  " required

" set the runtime path to include Vundle and initialize
set rtp+=~/.vim/bundle/Vundle.vim
call vundle#begin()
" alternatively, pass a path where Vundle should install plugins
"call vundle#begin('~/some/path/here')

" let Vundle manage Vundle, required
Plugin 'VundleVim/Vundle.vim'

" The following are examples of different formats supported.
" Keep Plugin commands between vundle#begin/end.
" plugin on GitHub repo
Plugin 'tpope/vim-fugitive'
" plugin from http://vim-scripts.org/vim/scripts.html
"Plugin 'L9'
" Git plugin not hosted on GitHub
"Plugin 'git://git.wincent.com/command-t.git'
" git repos on your local machine (i.e. when working on your own plugin)
"Plugin 'file:///home/gmarik/path/to/plugin'
" The sparkup vim script is in a subdirectory of this repo called vim.
" Pass the path to set the runtimepath properly.
Plugin 'rstacruz/sparkup', {'rtp': 'vim/'}
" Install L9 and avoid a Naming conflict if you've already installed a
" different version somewhere else.
Plugin 'ascenator/L9', {'name': 'newL9'}

"#####################################################################
"# Added by atul
"#####################################################################
"# Perl-Support - Perl IDE
Plugin 'vim-scripts/perl-support.vim'

"# Zoom in/out of windows
"# c-w o
Plugin 'vim-scripts/ZoomWin'

"# incremantal fuzzy search extension for
"# map z/ <Plug>(incsearch-fuzzy-/)
"# map z? <Plug>(incsearch-fuzzy-?)
"# map zg/ <Plug>(incsearch-fuzzy-stay)
Plugin 'haya14busa/incsearch-fuzzy.vim'

"# Eclipse like task list
"# \tl
Plugin 'vim-scripts/TaskList.vim'

"# Gundo.vim is Vim plugin to visualize your Vim undo tree.
"# :GundoShow
Plugin 'sjl/gundo.vim'

"# Perform all your vim insert mode completions with Tab
Plugin 'ervandew/supertab'

"# Syntax checking hacks for vim
"# SyntasticCheck for run checkers explicitly
Plugin 'scrooloose/syntastic'

"#
"Plugin 'jiangmiao/auto-pairs'

"# Vim bookmark plugin
"# mm BookmarkToggle     mi BookmarkAnnotate   mn/mp
"# ma showall            mc clear   mx clearall
"# #mkk #mjj #mg
Plugin 'MattesGroeger/vim-bookmarks'

"# This Vim plugin will pull C++ ptototypes into the implementation file
Plugin 'derekwyatt/vim-protodef'

"# :ack  [options] {pattern} [{directories}]  (ack installed on system
Plugin 'mileszs/ack.vim'

"# incrementally highlights ALL pattern matches unlike default 'incsearch'.
"# :incsearch-forward      :incsearchbackward     :insearch-stay
Plugin 'haya14busa/incsearch.vim'

"# Vim plugin that displays tags in a window, ordered by scope
"# :TagbarToggle
Plugin 'majutsushi/tagbar'

"# Automatically opens popup menu for completions
Plugin 'vim-scripts/AutoComplPop'

"# convenient ways to quickly reach the buffer/file/command/bookmark/tag you want
"# :FufBuffer/File/Dir/MRUFile/MRUCmd/BookMarkFile/BookMarkDir/*
Plugin 'vim-scripts/FuzzyFinder'

"# Plugin to manage Most Recently Used (MRU) files
"# :MRU
Plugin 'vim-scripts/mru.vim'

"# ENABLE as perl requirement
"# Clang completion plugin for vim
"# Require executable clang installed.
"#Plugin 'justmao945/vim-clang'

"# ENABLE as perl requirement and support of vim
"# Error : Compile vim with python support to use libclang
"# Clang executable is required for this.
"# this is autocomplete plugin for c, c++ lang
"#Plugin 'Rip-Rip/clang_complete'

"# Plugin to toggle, display and navigate marks
"# m, add               m. Toggle                   m- delete all
"# m<space> Delete from Current buff
"# ]` Jump to next mark     [` Jump to prev mark ]' Jump to start of next line containing a mark
"# [' Jump to start of prev line containing a mark
"# `] Jump by alphabetical order to next mark             `[           Jump by alphabetical order to prev mark
"# '] Jump by alphabetical order to start of next line having a mark
"# '[ Jump by alphabetical order to start of prev line having a mark
"# m/ Open location list and display marks from current buffer
Plugin 'kshenoy/vim-signature'

"#
"Plugin 'vim-scripts/OmniCppComplete'

"#
"Plugin 'fholgado/minibufexpl.vim'

"# A tree explorer plugin for vim.
"# :NERDTreeToggle
Plugin 'scrooloose/nerdtree'

"# A plugin of NERDTree showing git status flags. Works with the LATEST version of NERDTree.
Plugin 'Xuyuanp/nerdtree-git-plugin'

"# quoting/parenthesizing made simple
"# cs " '          cs ' <q>
"# ds "            ysiw] hellow=>[hellow]
"# cs]{  [hello]=>{Hello}
"# yssb or yss(
"# ysiw<em>
Plugin 'tpope/vim-surround'

"# Delete all the buffers except the current/named buffer
"# :BufOnly
"# :bufOnly <bufName/Number>
Plugin 'vim-scripts/BufOnly.vim'

"# The ultimate vim statusline utility.
Plugin 'Lokaltog/vim-powerline'

"# Fast file navigation for VIM
"# May required ruby
Plugin 'wincent/command-t'

"# Conque Shell : Run interactive commands inside a Vim buffer
"# :ConqueTerm bash
"# ConqueTerm Powershell.exe
Plugin 'vim-scripts/Conque-Shell'

"# Fuzzy file, buffer, mru, tag, etc finder
"# :CtrlP   <c-p>
"# :CtrlPBuffer/MRU/Mixed
"# Press <c-f> and <c-b> to cycle between modes.
"# Press <c-d> to switch to filename only search instead of full path.
"# Press <c-r> to switch to regexp mode.
"# Use <c-j>, <c-k> or the arrow keys to navigate the result list.
"# Use <c-t> or <c-v>, <c-x> to open the selected entry in a new tab or in a new
"# split.
"# Use <c-n>, <c-p> to select the next/previous string in the prompt's history.
"# Use <c-y> to create a new file and its parent directories.
"# Use <c-z> to mark/unmark multiple files and <c-o> to open them.
Plugin 'kien/ctrlp.vim'

"# Ultimate auto-completion system for Vim
Plugin 'Shougo/neocomplcache.vim'

"# Source code browser (supports C/C++, java, perl, python, tcl, sql, php, etc)
"# :Tlist
Plugin 'vim-scripts/taglist.vim'

"# A word fuzzy completion plugin for vim.
"# Type and press c-k
"# hellwo->Hellow
Plugin 'vim-scripts/Word-Fuzzy-Completion'

"#  manage your runtimepath
Plugin 'tpope/vim-pathogen'

"# Vim motion on speed!
"# \\w W S f F t T b B e E gE ge(end of word backword) j k n N
Plugin 'easymotion/vim-easymotion'

"# one colorscheme pack to rule them all!
Plugin 'flazz/vim-colorschemes'

"# Miscellaneous auto-load Vim scripts
Plugin 'xolox/vim-misc'

"# Extended session management for Vim
"# :SaveSession OpenSession RestartVim DeleteSession
Plugin 'xolox/vim-session'

"# lean & mean status/tabline for vim that's light as air
Plugin 'vim-airline/vim-airline'

"# Vim Better Whitespace Plugin
"# :ToggleWhitespace
"# :StripWhitespace
Plugin 'ntpeters/vim-better-whitespace'

"# Man page of any command SuperMan # <cmd>
"# SuperMan 2 pipe / SuperMan ls
Plugin 'jez/vim-superman'

"# Man page of any command :Man <cmd>
"# Man/Vman # cmd
"# :Mangrep
Plugin 'vim-utils/vim-man'

"# This plugin provides the following mappings which allow you to move between Vim panes and tmux splits seamlessly.
Plugin 'christoomey/vim-tmux-navigator'

"# Alternate Files quickly (open .h for .cpp or vise versa )
"# :A/AS/AV/AT/AN
"# :IH/IHS/IHV/IHT/IHN (switch to file under cursor)
"# :<Leader>ih switches to file under cursor
"# :<Leader>is switches to the alternate file f.h --> f.cpp
"# :<Leader>ihn cycles through matches
Plugin 'vim-scripts/a.vim'

"# A Vim plugin which shows a git diff in the gutter (sign column) and stages/undoes hunks.
"# :GitGutter
"# :let g:gitgutter_diff_base = '<commit SHA>'
Plugin 'airblade/vim-gitgutter'

"# Better JSON for VIM
Plugin 'elzr/vim-json'

"# HTML5 omnicomplete and syntax
Plugin 'othree/html5.vim'

"# Indent align the data on the basis of = or pattern
"# <,'>Tabularize /=     ==> test=1V => test    = 1V
"# <,'>Tabularize /=\zs  ==> test=1V => test=       1V
Plugin 'godlygeek/tabular'

"# A simple, easy-to-use Vim alignment plugin.
"# gaip= ga enable i inner p para = aligned with =
"# vipga= visual inner para ga =
"# gaip2= // use second = to align
"# gaip*= Around all occurrences
"# **= Left/Right alternating alignment around all occurrences
"# -<Space> Around the last occurrences
"# Reg ex gaip*^X regex =[;]*
"# vipga*= vipga**=
Plugin 'junegunn/vim-easy-align'

"# Align bases on chars
"# Select and :<,> align =
"# Select and :<,> Align = ; +
"
Plugin 'vim-scripts/Align'

"# Add comments
"# \cc //
"# \cn /* */
"# \c<space> Toggle
"# \cm minimal comment
Plugin 'scrooloose/nerdcommenter'

"# tcomment provides easy to use, file-type sensible comments for Vim
"# gc {count} {motion} Toggle Comment ex. gcG (it will comment current line to EOF;
"# gcc current line
"# gC comment by line wise
"# g> {count} {motion} comment ex. g>G (it will uncomment current line to EOF
"# g< {count} {motion} uncomment ex. g<G (it will uncomment current line to EOF
"# in insert mode <c_>2<c_>i
Plugin 'tomtom/tcomment_vim'

"# The ultimate undo history visualizer for VIM
"# UndotreeToggle
"#  Press ? in undotree window for quick help of hotkeys
Plugin 'mbbill/undotree'

"# Maintains a history of previous yanks, changes and deletes
"# :YRShow
"# : select and press enter
Plugin 'vim-scripts/YankRing.vim'

"# Multi cursor setting
"# start with F4 and f4 to continue (vimrc)
"# let g:multi_cursor_next_key='<C-n>'
"# let g:multi_cursor_prev_key='<C-p>'
"# let g:multi_cursor_skip_key='<C-x>' go to point and then skip
"# let g:multi_cursor_quit_key='<Esc>'
Plugin 'terryma/vim-multiple-cursors'

"Plugin 'paradigm/vim-multicursor'

"# An emacs-like mark multiple plugin,
"# key mapped to <leader>mm in vimrc
Plugin 'adinapoli/vim-markmultiple'

"# Key Mapping       Description
"# <count>ai         (A)n (I)ndentation level and line above.
"# <count>ii         (I)nner (I)ndentation level (no line above).
"# <count>aI         (A)n (I)ndentation level and lines above/below.
"# <count>iI         (I)nner (I)ndentation level (no lines above/below).
Plugin 'michaeljsmith/vim-indent-object'

"# Syntax highlighting, matching rules and mappings for the original Markdown and extensions.
Plugin 'gabrielelana/vim-markdown'
Plugin 'shime/vim-livedown'

"# C/C++ IDE -- Write and run programs. Insert statements, idioms, comments etc
"# :h csupport
Plugin 'vim-scripts/c.vim'
"Plugin 'MarcWeber/vim-addon-mw-utils'
"Plugin 'tomtom/tlib_vim'
"Plugin 'garbas/vim-snipmate'
"Plugin 'honza/vim-snippets'
Plugin 'Shougo/neocomplete.vim'

"# Vim sugar for the UNIX shell commands that need it the most. Features
"# include: Delete Unlink Move Rename Chmod Mkdir Find Locate Wall SudoWrite SudoEdit
Plugin 'tpope/vim-eunuch'

"# gitv is a repository viewer similar to gitk.
Plugin 'gregsexton/gitv'

"# uses the sign column to indicate added, modified and removed lines in a file that is managed by a version control system
Plugin 'mhinz/vim-signify'

"# An awesome automatic table creator & formatter allowing one to create neat tables as you type.
"# :TableModeToggle
"| Key  | action          |
"| \tm  | TableModeToggle |
"| |    | make table format |
"| \tdd | delete row      |
"| \tdc | delete column   |
"| [|   | move left       |
"| ]|   | move right      |
"| {|   | move up         |
"| }|   | move down       |
Plugin 'dhruvasagar/vim-table-mode'

"# Use for note creation
"# :Note
"#   @ automatically triggers tag completion
"#   ' becomes ‘ or ’ depending on where you type it
"#   " becomes “ or ” (same goes for these)
"#   -- becomes —
"#   -> becomes →
"#   <- becomes ←
"#   the bullets *, - and + become •
"#   the three characters *** in insert mode in quick succession insert a horizontal ruler delimited by empty lines
"#   Tab and Alt-Right increase indentation of  list items (works on the current line and selected lines)
"#   Shift-Tab and Alt-Left decrease indentation of list items
"#   Enter on a line with only a list bullet removes the bullet and starts a new line below the current line
"#   \en executes :NoteFromSelectedText
"#   \sn executes :SplitNoteFromSelectedText
"#   \tn executes :TabNoteFromSelectedText
Plugin 'xolox/vim-notes'

"# Switch between Header and Source file
"# :FSHere   :FSRight :FSSplitRight :FS[Split]Left/Above/Below
Plugin 'derekwyatt/vim-fswitch'

"#Help in editing of xml
Plugin 'othree/xml.vim'

"# Unobtrusive scratch window.
"# :Scratch
Plugin 'mtth/scratch.vim'

"# execute commands on tmux or screen
"# string and then ctrl-c ctrl-c to send string
Plugin 'jpalardy/vim-slime'

"# Run unite to display files and buffers as sources to pick from.
"# :Unite file buffer
"#
Plugin 'Shougo/unite.vim'

"# A powerful file explorer implemented in Vim script
"# :vimfiler
Plugin 'shougo/vimfiler.vim'

"# Asynchronous Lint Engine to show error while editing the files
"# Works on C,C++,perl, python, js, many laugs
"# Highlight error with >> in red bg
Plugin 'w0rp/ale'

"# lined diff in same buffer or different buffer on selection
"# Select line in visuals, :Linediff
"# Select other section    :Linediff
Plugin 'andrewradev/linediff.vim'

"# Simple Todo list
"# [ ] taskone
"#  [ ] subtask1
Plugin 'vitalk/vim-simple-todo'

"# Move buffers across multiple instances of Vim like modern browser
"# ToVim Session   :TransGetBuffer From Buff
"# FromVim Session :TransPutBuffer To Buffer
Plugin 'tyru/transbuffer.vim'

"# :Lynx index.html
Plugin 'vim-scripts/Lynx-Offline-Documentation-Browser'

"# buffer explorer \be \bs \bv
Plugin 'vim-scripts/bufexplorer.zip'

"# alternative to ack search subdir
Plugin 'rking/ag.vim'

"# Git methods
"# GitAdd\ga        GitDiff\gd              GitBlame\gb         GitPull          GitDiff --cached \gD
"# GitCommit\gc     GitCheckout             GitStatus\gs        GitLog\gl        GitPush
Plugin 'motemen/git-vim'

"# git branch info on status line
Plugin 'taq/vim-git-branch-info'

"# :Extradite toggles the Extradite buffer
"# oh, ov, and ot edit the revision under the cursor in a new horizontal / vertical / tab respectively.
"# dh, dv, and dt diff the current file against the revision under the cursor in a new horizontal / vertical / tab respectively.
"# t toggles the visibility of the file diff buffer.
"# q closes the Extradite buffer.
Plugin 'int3/vim-extradite'

"# used to open commit browser
"# :GV  to open commit browser
"# :GV! will only list commits that affected the current file
"# :GV? fills the location list with the revisions of the current file
Plugin 'junegunn/gv.vim'

"# Git Tree, Log and Diff plugin for vim.
Plugin 'vim-scripts/git-log'

"# Forget your curl today! Make HTTP requests from Vim without wrestling the command line!
"#  :HTTPClientDoRequest
"# # Second request.
"# :foo = bar
"# POST http://httpbin.org/post
"# {
"#   "data": ":foo",
"#    "otherkey": "hello"
"# }
Plugin 'aquach/vim-http-client'

"# solarized color theme
Plugin 'altercation/vim-colors-solarized'

"# better diff between files
"#:PatienceDiff - Use the Patience Diff algorithm for the next diff mode
"#
"#:EnhancedDiff <algorithm> - Use <algorithm> to generate the diff. Use any of
"#    myers         Default Diff algorithm used
"#    default       Alias for myers algorithm
"#    histogram     Fast version of patience algorithm
"#    minimal       Default diff algorithm, trying harder to minimize the diff
"#    patience      Patience diff algorithm.
"#
Plugin 'chrisbra/vim-diff-enhanced'

"# Do for Vim
"# Run asynchronous shell commands and display the output
"# :Do cmd
"# :DoQuietly
"# :Doing
"# :Done
"# '<,'>DoThis
"# :DoAgain (run last command)
Plugin 'joonty/vim-do'


"# jedi-vim - awesome Python autocompletion with VIM
"
"# Completion <C-Space>
"# Goto assignments <leader>g (typical goto function)
"# Goto definitions <leader>d (follow identifier as far as possible,
"# includes imports and statements)
"# Show Documentation/Pydoc K (shows a popup with assignments)
"# Renaming <leader>r
"# Usages <leader>n (shows all the usages of a name)
"# Open module, e.g. :Pyimport os (opens the os
"# module)
"#
Plugin 'davidhalter/jedi-vim'

"# *** Not working on windows so disabled it
"# Fuzzy file and folder search
"# Files [PATH] 	Files (similar to :FZF)
"# GFiles [OPTS] 	Git files (git ls-files)
"# GFiles? 	Git files (git status)
"# Buffers 	Open buffers
"# Colors 	Color schemes
"# Ag [PATTERN]  ag seach result
Plugin 'junegunn/fzf.vim'

"# vim plug-in which provides support for expanding abbreviations similar to emmet.
Plugin 'mattn/emmet-vim'

"# Templates plugin to load templates on file
"# :TemplateInit in newly opened file.
"# :TemplateInit cpp, :TemplateInit main.cpp
Plugin 'tibabit/vim-templates'

"#  shows a file in multiple windows, with each sequential window showing
"sequential lines of text, rather like a book.
"# :MPageToggle
Plugin 'lacombar/vim-mpage'

"# To open DirDiff from the command line, run vim -c "DirDiff dir1 dir2"
Plugin 'will133/vim-dirdiff'

" #
" # Enabled only on required system, else default disabled for large setups
"Plugin 'SirVer/ultisnips'
"Plugin 'Valloric/YouCompleteMe'

" # This is NetBackup code formating
" # Read src/_vimrc_local.vim file for more details present in the master
" # add below entry into local vimrc file
" # call lh#local_vimrc#munge('whitelist', '/path-to-your-sandbox/src')
Plugin 'LucHermitte/lh-vim-lib'
Plugin 'LucHermitte/local_vimrc'

" Temporarily disabled. Enable the same when go language support is required
"" # This plugin adds Go language support for Vim
""
"Plugin 'fatih/vim-go'

" Temporarily disabled. Enable the same when go language support is required
"" # Intellisense engine
"" # " Use <c-space> to trigger completion.
"" # inoremap <silent><expr> <c-space> coc#refresh()
"" # Fix: :call coc#util#install()
"" # If above line is not fixing the issue, go to bundle/coc.nvim and
"" run 'git checkout release' command
"Plugin 'neoclide/coc.nvim', {'branch': 'release'}
"Plugin 'neoclide/coc-python'
"Plugin 'neoclide/coc-css'
"Plugin 'neoclide/coc-highlight'

" # A vim plugin wrapper for prettier, pre-configured with custom default
" prettier settings.
" # Prettier by default will run on auto save but can also be manually
" # triggered by:  <Leader>p
Plugin 'prettier/vim-prettier'


" # A vim plugin to open file having format file:line
Plugin 'bogado/file-line'

"filetype plugin on
"
" Brief help
" :PluginList       - lists configured plugins
" :PluginInstall    - installs plugins; append `!` to update or just
" :PluginUpdatea - perform manually *******************************
" :PluginSearch foo - searches for foo; append `!` to refresh local cache
" :PluginClean      - confirms removal of unused plugins; append `!` to
" auto-approve removal
"
" see :h vundle for more details or wiki for FAQ
" Put your non-Plugin stuff after this line

" This plugin will help to replace string with keeping case as it is
" ABC => AXY
" Abc => Xyz
" abc => xyz
" aBc X  xYz
" Ex :%S/abc/xyz/gi
Plugin 'tpope/vim-abolish'

" The plugin is designed to automatically rename closing HTML/XML tags
" when editing opening ones (or the other way around)."
Plugin 'AndrewRadev/tagalong.vim'

" for CSS
Plugin 'wavded/vim-stylus'
Plugin 'skammer/vim-css-color'
" for HTML
Plugin 'digitaltoad/vim-pug'
Plugin 'adelarsq/vim-matchit'
" for js script
Plugin 'jelera/vim-javascript-syntax'
Plugin 'pangloss/vim-javascript'

"On Windows Cygwin platform use below command to install all plugins under
"~/.vim/bundle folder
"for p in `egrep "^Plugin" ~/.vim/vundle.vimrc  | sed -e"s/Plugin //" | awk
"-F"'" '{print $2;}'`; do git clone  https://github.com/${p}; done
