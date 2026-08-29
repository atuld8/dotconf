" Filetype plugin: folding + navigation for eTrack reports

if exists("b:loaded_ftplugin_etrack_report")
  finish
endif
let b:loaded_ftplugin_etrack_report = 1

setlocal nowrap
setlocal foldmethod=expr
setlocal foldexpr=EtrackReportFoldLevel(v:lnum)
setlocal foldnestmax=2
setlocal foldlevel=1
setlocal foldcolumn=2

" Level 1: hierarchy / deliverable summary / each EEB version report
" Level 2: SUMMARY, SR DETAILS, shipping, packages, links, artifacts
function! EtrackReportFoldLevel(lnum)
  let line = getline(a:lnum)

  if line =~# '^EEB \(PACKAGE\|BUNDLE\|STANDARD EEB\) REPORT'
    return '>1'
  endif
  if line =~# '^DELIVERABLE SUMMARY'
    return '>1'
  endif
  if line =~# '^HIERARCHY TREE:$'
    return '>1'
  endif
  if line =~# '^| INCIDENT'
    return '>1'
  endif

  if line =~# '^\(SUMMARY:\|LINKS:\|VERSION SUMMARY:\)$'
    return '>2'
  endif
  if line =~# '^\(SR SHIPPING SUMMARY:\|ARTIFACTS SUMMARY:\|PLATFORM PACKAGES SUMMARY:\)$'
    return '>2'
  endif
  if line =~# '^\(SR DETAILS (\|SR SHIPPING (\|PLATFORM PACKAGES (\|ARTIFACTS (\|^SR SHIPPING DETAILS (\|^ARTIFACTS (\|^PLATFORM PACKAGES (\)'
    return '>2'
  endif

  return '='
endfunction

function! EtrackReportFoldSummaries()
  setlocal foldlevel=1
endfunction

function! EtrackReportFoldSections()
  setlocal foldlevel=2
endfunction

function! EtrackReportUnfoldAll()
  setlocal foldlevel=99
endfunction

function! EtrackReportFoldAll()
  setlocal foldlevel=0
endfunction

" Jump between major report blocks
function! EtrackReportNextReport()
  if search('^EEB \(PACKAGE\|BUNDLE\|STANDARD EEB\) REPORT\|^DELIVERABLE SUMMARY\|^HIERARCHY TREE:\|^| INCIDENT', 'W')
    normal! zt
  endif
endfunction

function! EtrackReportPrevReport()
  if search('^EEB \(PACKAGE\|BUNDLE\|STANDARD EEB\) REPORT\|^DELIVERABLE SUMMARY\|^HIERARCHY TREE:\|^| INCIDENT', 'bW')
    normal! zt
  endif
endfunction

nnoremap <buffer> <LocalLeader>z1 :call EtrackReportFoldSummaries()<CR>
nnoremap <buffer> <LocalLeader>z2 :call EtrackReportFoldSections()<CR>
nnoremap <buffer> <LocalLeader>za :call EtrackReportUnfoldAll()<CR>
nnoremap <buffer> <LocalLeader>zA :call EtrackReportFoldAll()<CR>
nnoremap <buffer> <LocalLeader>]r :call EtrackReportNextReport()<CR>
nnoremap <buffer> <LocalLeader>[r :call EtrackReportPrevReport()<CR>

" Standard fold keys still work: za zc zo zC zM zR zm zr

if exists(':TableModeEnable')
  TableModeEnable
endif
