" Markdown folding by ATX headings (# .. ######)
" Works with etrack_hierarchy_table.py -M output and any Markdown file.

if !exists("g:etrack_markdown_fold_setup")
  let g:etrack_markdown_fold_setup = 1

  function! MarkdownHeadingFoldLevel(lnum)
    let line = getline(a:lnum)
    if line =~# '^#{1,6} '
      return '>' . (len(matchstr(line, '#*')) - 1)
    endif
    return '='
  endfunction
endif

setlocal foldmethod=expr
setlocal foldexpr=MarkdownHeadingFoldLevel(v:lnum)
setlocal foldnestmax=6
setlocal foldcolumn=2

" Start with level-1 sections open (## folded, # open)
if &foldlevel == 0
  setlocal foldlevel=1
endif

" Buffer-local navigation (same keys as etrack-report ftplugin)
nnoremap <buffer> <LocalLeader>z1 :setlocal foldlevel=1<CR>
nnoremap <buffer> <LocalLeader>z2 :setlocal foldlevel=2<CR>
nnoremap <buffer> <LocalLeader>za :setlocal foldlevel=99<CR>
nnoremap <buffer> <LocalLeader>zA :setlocal foldlevel=0<CR>
