if has('win32') || has('win64')
  set runtimepath=$HOME/.vim,$VIM/vimfiles,$VIMRUNTIME,$VIM/vimfiles/after,$HOME/.vim/after
  let g:jedi#auto_initialization = 0
endif

call pathogen#infect()
"call pathogen#runtime_append_all_bundles()
call pathogen#helptags()

" This is to display special charactors which not getting displayed with
" nornaml mode
set encoding=UTF-8

filetype plugin on
filetype indent on

set nu
set relativenumber
autocmd WinEnter,FocusGained * if (!(expand('%') =~ 'NERD_tree')) | setlocal number relativenumber | endif
autocmd WinLeave,FocusLost   * if (!(expand('%') =~ 'NERD_tree')) | :setlocal number norelativenumber | endif
let NERDTreeShowLineNumbers=0
set tabstop=4
set shiftwidth=4
set expandtab
"retab
" on set list ">  " will be displayed
set listchars=eol:\$\,trail:.,extends:>,precedes:<,tab:\>\
"set list

set ai
set cindent
set ruler
set backspace=2
set history=50
set formatoptions=tcql
set hlsearch
set ignorecase
set laststatus=2
set incsearch
" To display full path on screen
set statusline+=%F


" this will work in all cases
set cursorline
autocmd WinEnter * setlocal cursorline
autocmd WinLeave * setlocal nocursorline
hi Search cterm=NONE ctermfg=grey ctermbg=magenta


""if light color background
function! CursorLineL ()
   hi CursorLine   cterm=NONE ctermbg=lightgrey guibg=lightgrey
endfunction

""if dark color background
function! CursorLineD ()
   hi CursorLine  term=NONE cterm=NONE ctermbg=233 guibg=Grey20
endfunction
"hi CursorLine   cterm=NONE ctermbg=darkred ctermfg=white
""if light color background

" set background=light
command! CurD call CursorLineD()
command! CurL call CursorLineL()

if &background == "dark"
   call CursorLineD()
else
   call CursorLineL()
endif

function! OverLen()
    if &background == "dark"
        "if dark color background
        highlight OverLength ctermbg=red ctermfg=white guibg=#592929
    endif
    match OverLength /\%81v.\+/
endfunction

function! ClearQuickfixList()
  call setqflist([])
endfunction
command! ClearQuickfixList call ClearQuickfixList()
command! VimGrepCursorw :execute 'vimgrep '.expand('<cword>').' '.fnameescape(expand('%:p')) | :copen | :cc
command! VimGrepCursorW :execute 'vimgrep '.expand('<cWORD>').' '.fnameescape(expand('%:p')) | :copen | :cc
command! VimGrepYanked :execute 'vimgrep /'.@0.'/ '.fnameescape(expand('%:p')) | :copen | :cc
command! VimGrepError :execute 'vimgrep /\<\(FATAL\|ERROR\|ERRORS\|FAIL\|FAILED\|FAILURE\)\>/ '.fnameescape(expand('%:p')) | :copen | :cc
command! VimGrepWarn :execute 'vimgrep /\<\(WARNING\|DELETE\|DELETING\|DELETED\|RETRY\|RETRYING\|Diagnostic\)\>/ '.fnameescape(expand('%:p')) | :copen | :cc
command! VimGrepErrorAppend :execute 'vimgrepadd /\<\(FATAL\|ERROR\|ERRORS\|FAIL\|FAILED\|FAILURE\)\>/ '.fnameescape(expand('%:p')) | :copen | :cc
command! VimGrepWarnAppend :execute 'vimgrepadd /\<\(WARNING\|DELETE\|DELETING\|DELETED\|RETRY\|RETRYING\|Diagnostic\)\>/ '.fnameescape(expand('%:p')) | :copen | :cc
command! Nblog :execute 'source ~/.vim/syntax/nblog.vim'


command! CurrentFilePathCopy :let @+=expand("%:p")
command! CurrentFileDirCopy  :let @+=expand("%:p:h")

" Convert slashes to backslashes for Windows.
if has('win32')
    nmap ,cs :let @*=substitute(expand("%"), "/", "\\", "g")<CR>
    nmap ,cl :let @*=substitute(expand("%:p"), "/", "\\", "g")<CR>
    nnor ,yf :let @"=substitute(expand("%:p"), "/", "\\", "g")<CR>
    nmap ,yn :let @"=substitute(expand("%"), "/", "\\", "g")<CR>

    " This will copy the path in 8.3 short format, for DOS and Windows 9x
    nmap ,c8 :let @*=substitute(expand("%:p:8"), "/", "\\", "g")<CR>
else
    nmap ,cs :let @*=expand("%")<CR>
    nmap ,cl :let @*=expand("%:p")<CR>
    nnor ,cf :let @*=expand("%:p")<CR>    " Mnemonic: Copy File path
    nnor ,yf :let @"=expand("%:p")<CR>    " Mnemonic: Yank File path
    nnor ,fn :let @"=expand("%")<CR>      " Mnemonic: yank File Name
endif

if  has('nvim')
    set ttyfast
else
    set ttyfast
    set ttyscroll=3
    if has("Unix")
       set term=screen-256color
    endif
endif

if has("Win32")
    set guifont=consolas:h10
    call CursorLineL()
    "set guifont=fixed613:h13
else
    if has ("gui_running")
        "set guifont=monaco:h11
        "set guifont=menlo\ regular:h12
        "set guifont=Consolas:h12
        set guifont=6x13:h13
    endif
endif

source ~/.vim/cscope_maps.vim

" quick copy current buffer to next window
let  @c="ggVGyggVGp"
" quick copy opposite buffer to current buffer
let  @n="ggVGyggVGp"

if &diff
    nmap mo do]c
    nmap mp dp]c
    autocmd VimResized * wincmd =
    highlight DiffAdd    cterm=bold ctermfg=10 ctermbg=17 gui=none guifg=bg guibg=Red
    highlight DiffDelete cterm=bold ctermfg=10 ctermbg=17 gui=none guifg=bg guibg=Red
    highlight DiffChange cterm=bold ctermfg=10 ctermbg=17 gui=none guifg=bg guibg=Red
    highlight DiffText   cterm=bold ctermfg=10 ctermbg=88 gui=none guifg=bg guibg=Red
elseif has ("gui_running")
"    colorscheme torte
    "colorscheme zellner
    " for fast scolling
    set scrolljump=5
    execute "set scroll=" . &lines / 3
endif

nmap <F2> :help <C-R><C-W><CR>

vnoremap < <gv
vnoremap > >gv

let g:pydiction_location = '~/.vim/bundle/pydiction/complete-dict'
let g:pydiction_menu_height = 3

" open file in readonly mode if already swap is present
autocmd SwapExists * let v:swapchoice = "o"

map <C-L> <C-W>\|<C-W>_
map <leader>fb :FufBuffer<CR>
map <leader>ff :FufFile<CR>

"Some buffer shortcuts

nmap <leader>bl :buffers<CR>
nmap <leader>bd :bd<CR>
nmap <leader>bn :bnext<CR>
nmap <leader>bp :bprev<CR>

"for Windows
"if has("gui_running")
"                " settings for gvim
"elseif &term =~ 'xterm' || term =~ '^vt\d\d\d'
"                " settings for xterm and vtnnn
"elseif &term == 'win32'
"  " settings for the Dos Box in Windows
"  set lines=9999
"  set columns=9999
" else do nothing
"endif

"Pass argument to vim command -c "command" -n no swap and -p "tabs" filenames
" vim -c "set nu" -n -p "*.txt"

map <F10> :<C-u>let @z=&so<CR>:set so=0 noscb<CR>:bo vs<CR>Ljzt:setl scb<CR><C-w>p:setl scb<CR>:let &so=@z<CR>


function! F_ctag_cscope_add()
  let s:path = fnamemodify(resolve(expand('<sfile>:p')), ':h')
  let s:srcpath = substitute(s:path, '\/src\/.*$', '\/src\/',"")
  let s:cscope_out = substitute(s:srcpath, '\/src\/.*$', '\/src\/cscope.out',"")
  let s:ctags_file = substitute(s:srcpath, '\/src\/.*$', '\/src\/vtags',"")

  if filereadable(s:cscope_out)
    exec ":cscope add " . s:cscope_out
  endif

  if filereadable(s:ctags_file)
    exec ":set tags+=" . s:ctags_file
  endif
endfunction

call F_ctag_cscope_add()

function! F_ctag_cscope_add_wrt_git()
  let s:rootpath = system('git rev-parse --show-toplevel')
  let s:cscope_out = substitute(s:rootpath, '\n$', '/cscope.out',"")
  let s:ctags_file = substitute(s:rootpath, '\n$', '/tags',"")

  if filereadable(s:cscope_out)
    if has('win32') || has('win64')
      exec  ":cscope.exe add " . s:cscope_out
    else
      exec  ":cscope add " . s:cscope_out
    endif
  endif

  if filereadable(s:ctags_file)
    exec ":set tags+=" . s:ctags_file
  endif
endfunction

call F_ctag_cscope_add_wrt_git()

function! F_include_project_speicific_vimrc()
  let s:rootpath = system('git rev-parse --show-toplevel')
  let s:rootpathtrim = substitute(s:rootpath, '\n$', '', "")
  let s:local_vimrc = substitute(s:rootpath, '\n$', '/.vimrc',"")

  if isdirectory(s:rootpathtrim)
    exec ":let g:git_root_path=\"".s:rootpathtrim."\""
    exec ":set path+=". s:rootpathtrim
  else
    exec "let g:git_root_path=\".\""
  endif

  if filereadable(s:local_vimrc)
    if has('win32') || has('win64')
      exec  ":source " . s:local_vimrc
    else
      exec  ":source " . s:local_vimrc
    endif
  endif
endfunction


source ~/.vim/omnicppSettings.vim

"if filereadable("./add_header.vim")
"    source ./add_header.vim
"endif
"if filereadable("../add_header.vim")
"    source ../add_header.vim
"endif

function! FunKey6()
    if &filetype == 'c' || &filetype == 'cpp'
        :execute "!clear && g++ -Wall -o" . expand("%:p:r"). " ". expand("%") " && ".expand("%:p:r")
    else
       if &filetype == 'python'
           :exe "!clear && python ".expand("%:p")
       endif
    endif
    if &filetype == 'java'
       :exe "!clear && javac ". expand("%") . " && java ".expand("%:r")
    endif
endfunction

function! CtrlFunKey6()
    if &filetype == 'c' || &filetype=='cpp'
        :exec "silent !clear && g++ -Wall -g -o" . expand("%:p:r"). " ". expand("%") " && ".expand("%") " > ".expand("%:p:r") .".output 2>&1"
            :exec "split ".expand("%:p:r") .".output"
    else
       if &filetype == 'python'
           :exe "new | !clear && python ".expand("%:p")
       endif
    endif
    if &filetype == 'java'
       :exe "!clear && javac ". expand("%") . " && java ".expand("%:r")
    endif
endfunction

function! FunKey7()
    if &filetype == 'c' || &filetype == 'cpp'
        :execute "!clear && g++ -Wall -o" . expand("%:p:r"). " ". expand("%") " && echo -n 'Enter arguments: ' && read arguments && ".expand("%:p:r"). " $arguments"
    else
       if &filetype == 'python'
           :exe "!clear && echo -n 'Enter arguments: ' && read arguments && python ".expand("%:p"). " $arguments"
       endif
    endif
endfunction
"autocmd BufNewFile,BufReadPost *.py :set filetype='py'

command!  VimNotes       :sp ~/.vim/vundle.vimrc | vsp ~/.vim/doc/vi.shortcuts.info_enc.txt
command!  VundleFile     :sp ~/.vim/vundle.vimrc
command!  ViShortcutinfo :vsp ~/.vim/doc/vi.shortcuts.info_enc.txt
command!  Vimrc          :sp ~/.vim/vimrc

if has('win32') || has('win64')
    command!  Vimrcl :sp ~/_vimrc
    command!  VimrclApply :source ~/_vimrc
else
    command!  Vimrcl :sp ~/.vimrc
    command!  VimrclApply :source ~/.vimrc
endif

"map <F6> :execute "!clear && g++ -o" . expand("%:p:r"). " ". expand("%") " && ".expand("%:p:r")<CR>
map <F6>   :call FunKey6()<CR>
map <C-F6> :call CtrlFunKey6()<CR>
"map <F7> :execute "!clear && g++ -o" . expand("%:p:r"). " ". expand("%") " && echo -n 'Enter arguments: ' && read arguments && " .expand("%:p:r")." $arguments"<CR>
map <F7>   :call FunKey7()<CR>
if has('unix') || has('win32unix')
    map <F8>   :execute "!clear && g++ -g3 -o" . expand("%:p:r"). " ". expand("%") " && gdb ".expand("%:p:r").""<CR>
endif
if has('mac')
    map <F8>   :execute "!clear && g++ -g3 -o" . expand("%:p:r"). " ". expand("%") " && lldb ".expand("%:p:r").""<CR>
endif
map <F9>   :execute "!clear && g++ -o" . expand("%:p:r"). " ". expand("%")<CR>

"au BufWritePost *.c,*.cpp,*.h exec "silent ! ctags -R -o ". expand("%:p:r"). ".tags "
"&& :set tags+= ". expand("%:p:r").".tags"
"au BufReadPost *.c,*.cpp,*.h exec "silent !ctags -o ". expand("%:p:r"). ".tags && :set tags+= ". expand("%:p:r").".tags"

"au BufWritePost *.c,*.cpp,*.h exec "!echo ". expand("%:p"). " | ctags -o ". expand("%:p:r"). ".tags -L - "
"au BufReadPost *.c,*.cpp,*.h exec ":set tags+=".expand("%:p:r").".tags"
let g:C_TemplateOverwrittenMsg= 'no'
let g:C_LocalTemplateFile= '~/.vim/template/Templates'
if filereadable("template/company.cxx")
    autocmd BufNewFile  *.c,*.cpp,*.h 0r ~/.vim/template/company.cxx
endif


let opensslargs='x509 -text -noout -fingerprint -sha1 -in #'
let opensslchainarg1='crl2pkcs7 -nocrl -certfile #'
let opensslchainarg2=' pkcs7 -print_certs -text -noout'
"on certificate open it convert into x509 readable format
au BufReadPost,BufNewFile *.0 vnew %.x509 | r!openssl x509 -text -noout -fingerprint -sha1 -in #
command! GenX509 execute ":vnew | r!openssl " opensslargs
command! GenX509chain execute ":vnew | r!openssl " opensslchainarg1 " | openssl " opensslchainarg2
if has('win32') || has('win64')
    command! GenX509Nb execute ":vnew | r!vxsslcmd.exe " opensslargs
    command! GenX509chainNb execute ":vnew | r!vxsslcmd.exe " opensslchainarg1 " | vxsslcmd.exe " opensslchainarg2
else
    command! GenX509Nb execute ":vnew | r!/usr/openv/netbackup/bin/goodies/vxsslcmd " opensslargs
    command! GenX509chainNb execute ":vnew | r!/usr/openv/netbackup/bin/goodies/vxsslcmd " opensslchainarg1 " | /usr/openv/netbackup/bin/goodies/vxsslcmd" opensslchainarg2
endif

let @o=':only0v$"zy:sp zkb:wincmd _'
let @t=':only0v$"zy:tabedit zkb'
let @p='0v$"zy:sp zkb:wincmd _'
"let @v=':BufOnly0v$y:vsp 0kb | bN:wincmd l:bn:wincmd |:vertical resize -70'
let @v=':BufOnly0v$"zy:vsp zkb | bN:wincmd r:bn:wincmd |:vertical resize -70'
"let @w=':0v$"zy:wincmd w:sp zkb | bN:wincmd r'
":wincmd r:bn:wincmd |:vertical resize -70'
"let @w='0v$"zy:vsp zkb | bN:wincmd l:buffer 1'
let @w='0v$"zy:wincmd w:sp zkb'
let @x='0v$"zy:wincmd w:vsp zkb:wincmd p'

" Insert the new uuid in insert mode
imap <c-j>u <c-r>=toupper(substitute(system('uuidgen'),'\n','','g'))<cr>

"Better copy and paste
set pastetoggle=<F2>
if $TMUX == ''
    set clipboard+=unnamed
endif

let  g:C_UseTool_cmake    = 'yes'
let  g:C_UseTool_doxygen = 'yes'


" this is for EasyMotion
let g:EasyMotion_leader_key = '\\'

if has("wildmenu")
    set wildmenu wildmode=longest:full,full
endif
if !has("gui_running")
    runtime! menu.vim
    set wildcharm=<C-]>
    map <C-Z> :emenu <C-]>
    map! <C-Z> <C-O>:emenu <C-]>
endif

let g:snips_author = ' Atul Das'


if filereadable("/usr/local/bin/ctags")
   let Tlist_Ctags_Cmd = '/usr/local/bin/ctags'
endif
let Tlist_WinWidth = 50
let Tlist_Use_Right_Window=1

" Disabled auto popup, use tab or C-N C-X C-O to autocomplete
let g:clang_complete_auto = 0

"show clang errors in the quickfix windows
let g:clang_complete_copen = 1

"list the files and folder in tree style if NERDTree not exist
let g:netrw_liststyle=3
let g:NERDTreeWinPos = "right"
let g:tagbar_left=1
let g:tagbar_width=30
let g:tagbar_autofocus=1
let g:tagbar_autoclose=0
nmap <Leader>st :TagbarToggle<CR>
autocmd BufEnter * silent! lcd %:p:h

if !exists('g:nerdtreefindexec')
    let g:nerdtreefindexec = 0
endif
function! F_toggle_nerdtree_settings()
    if g:nerdtreefindexec == 1
        let g:nerdtreefindexec = 0
        NERDTreeClose
        wincmd p
    else
        let g:nerdtreefindexec = 1
        NERDTreeToggle
        NERDTreeFind
        wincmd p
    endif
endfunction

function! GitShowMakeprg()
    set makeprg=git\ show\ --name-only\ --oneline\ $*\ \\\|\ tail\ -n\ +2
    set efm+=%f
    make
endfunction

command! -complete=shellcmd -nargs=+ Shell call s:RunShellCommand(<q-args>)
function! s:RunShellCommand(cmdline)
    echo a:cmdline
    let expanded_cmdline = a:cmdline
    for part in split(a:cmdline, ' ')
        if part[0] =~ '\v[%#<]'
            let expanded_part = fnameescape(expand(part))
            let expanded_cmdline = substitute(expanded_cmdline, part, expanded_part, '')
        endif
    endfor
    botright new
    setlocal buftype=nofile bufhidden=wipe nobuflisted noswapfile nowrap
    call setline(1, 'You entered:    ' . a:cmdline)
    call setline(2, 'Expanded Form:  ' .expanded_cmdline)
    call setline(3,substitute(getline(2),'.','=','g'))
    execute '$read !'. expanded_cmdline
    setlocal nomodifiable
    1
endfunction

command! -complete=file -nargs=* GitCmd call s:RunShellCommand('git '.<q-args>)

" NERDTree is disabled by default
"let g:nerdtreefindexec=0
nmap <Leader>sn :silent call F_toggle_nerdtree_settings()<CR>
command! NERDTreeFindExeOff :let g:nerdtreefindexec=0
command! NERDTreeFindExeOn  :let g:nerdtreefindexec=1
if !&diff && g:nerdtreefindexec == 1
    autocmd BufLeave * if (g:nerdtreefindexec == 1 && !(expand('%') =~ 'NERD_tree')) | silent! NERDTreeFind | wincmd p | endif
    autocmd BufEnter * if (g:nerdtreefindexec == 1 && (!(expand('%') =~ 'NERD_tree')) && (!(expand('#') =~ 'NERD_tree' )) && filereadable(fnameescape(expand('%')))) | silent! NERDTreeFind |  wincmd p | endif

    "Start NERDTree & Jump to the main window.
    autocmd VimEnter * if (g:nerdtreefindexec == 1 && !(expand('%') =~ 'NERD_tree')) | NERDTree | wincmd p | endif
    "close vim if the only window left open is a NERDTree
    autocmd BufEnter * if (winnr("$") == 1 && exists("b:NERDTree") && b:NERDTree.isTabTree()) | q | endif
endif

"On terminal the special chars not working as arrow, to make it compatible
let g:nerdtree_tabs_open_on_console_startup = 0
let g:NERDTreeDirArrowExpandable            = ">"
let g:NERDTreeDirArrowCollapsible           = "v"
let g:NERDTreeIgnore                        = ['\~$','\.pyc$','__pycache__']

source ~/.vim/vundle.vimrc

source ~/.vim/neovimrc

source ~/.vim/fuzzysearch.vim


autocmd FileType c set makeprg=clear\ &&\ gcc\ -g\ -Wall\ -o\ %:p:h/Build/%:t:r\ %
autocmd FileType c syntax on
autocmd FileType cpp set makeprg=clear\ &&\ g++\ -g\ -Wall\ -o\ %:p:h/Build/%:t:r\ %
autocmd FileType cpp syntax on

autocmd FileType css set omnifunc=csscomplete#CompleteCSS

function! RunProgram(...)
    exec ":!%:p:h/Build/%:t:r " a:000
endfunction

command! -nargs=* Run call RunProgram(<f-args>)

augroup perl_ft
  autocmd!
  autocmd fileType perl set makeprg=perl\ -c\ %\ $*
  autocmd FileType perl set errorformat=%f:%l:%m
  autocmd FileType perl set showmatch
  autocmd FileType perl let perl_extended_vars = 1
augroup END

augroup python_ft
  autocmd!
  au FileType python set makeprg=pylint\ --reports=n\ --output-format=parseable\ %:p
  au FileType python set efm=%A%f:%l:\ [%t%.%#]\ %m,%Z%p^^,%-C%.%#
  au FileType python let python_highlight_all = 1
  au FileType python syntax on
  au BufNewFile,BufRead *.py
       \ set tabstop=4 |
       \ set softtabstop=4 |
       \ set shiftwidth=4 |
       \ set textwidth=79 |
       \ set expandtab |
       \ set autoindent |
       \ set fileformat=unix |
augroup END

augroup yaml_ft
  autocmd!
  au FileType yaml let g:syntastic_yaml_checkers = ['yamllint']
  au FileType yaml setlocal ts=2 sts=2 sw=2 expandtab
  au FileType yaml let g:indentLine_char = '|'
augroup END

syntax on

" WiX files are XML
augroup wix_ft
  autocmd!
  autocmd BufNewFile,BufRead *.wxs set filetype=xml
augroup END

augroup groovy_ft
  autocmd!
  autocmd BufNewFile,BufRead *.gradle set filetype=groovy
augroup END

" setting for vim-session
let g:session_autosave='no'
let g:session_autoload='no'

"Keymaps for multicursor
"let g:multicursor_quit = "\<Esc>"
"nnoremap <Leader><C-m>p :call MultiCursorPlaceCursor()<Cr>
"nnoremap <Leader><C-m>r :call MultiCursorRemoveCursors()<Cr>
"nnoremap <Leader><C-m>m :call MultiCursorManual()<Cr>
"nnoremap <Leader><C-m>v :call MultiCursorVisual()<Cr>
"xnoremap <Leader><C-m>s :call MultiCursorSearch('')<Cr>
"

" Map start key separately from next key
 let g:multi_cursor_start_key='<F4>'


let g:mark_multiple_trigger = "<leader>mm"
let g:yankring_replace_n_nkey = "<leader>mmn"
let g:yankring_replace_n_pkey = "<leader>mmp"


" Start interactive EasyAlign in visual mode (e.g. vipga)
xmap ga <Plug>(EasyAlign)
"
" Start interactive EasyAlign for a motion/text object (e.g. gaip)
nmap ga <Plug>(EasyAlign)

command! -range -nargs=0 -bar JsonTool <line1>,<line2>!python -m json.tool

" Just to avoid warning
let g:ale_emit_conflict_warnings = 0

" Custom maps for specific work
inoremap \fp <C-R>=getcwd()<CR>

" Custm map for TAR foldeing
let @t="/TAR STARTEDzf/TAR exitj"

command! -nargs=+ Calc :py print <args>
"py from math import *

nnoremap <C-W>z :call MaximizeToggle()<CR>
function! MaximizeToggle()
  if exists("s:maximize_session")
    exec "source " . s:maximize_session
    call delete(s:maximize_session)
    unlet s:maximize_session
    let &hidden=s:maximize_hidden_save
    unlet s:maximize_hidden_save
  else
    let s:maximize_hidden_save = &hidden
    let s:maximize_session = tempname()
    set hidden
    exec "mksession! " . s:maximize_session
    only
  endif
endfunction

"Some setting which will allow find to search all sub-subdirctories
set path+=**

let g:syntastic_cpp_compiler_options = '-Wall'
let g:syntastic_c_compiler_options = '-Wall'

" Data for template plugin
let g:tmpl_auto_initialize = 0
let g:tmpl_author_name     = 'atuld8'
let g:tmpl_author_email    = 'atuld8@gmail.com'
let g:tmpl_company         = '<company private ltd.>'

command! -nargs=1 SilentCmd execute ':silent !'.<q-args> | execute ':redraw!'
"Example
"command! Makeall :SilentCmd tmux send -t 2 'make ; make.suse' Enter

" Setting the buffer list as default option for ctrlp plugin
let g:ctrlp_cmd = 'CtrlPBuffer'

" This must be last line as this will overwrite default settings by local
" vimrc
call F_include_project_speicific_vimrc()
" vim: set ts=2 sw=2 et:
