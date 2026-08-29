" Detect eTrack report buffers by filename or content.

augroup etrack_report_detect
  autocmd!
  autocmd BufRead,BufNewFile dump,*.etr,*.etrack,*.etreport setfiletype etrack-report
  autocmd BufRead,BufNewFile *.etreport.md,*.etrack.md setfiletype markdown
  autocmd BufRead * call s:DetectEtrackReport()
augroup END

function! s:DetectEtrackReport()
  if &filetype ==# 'markdown'
    return
  endif
  if &filetype !=# '' && &filetype !=# 'etrack-report'
    return
  endif
  let max = min([80, line('$')])
  for i in range(1, max)
    let line = getline(i)
    if line =~# '^# \(EEB \|Hierarchy\|DELIVERABLE SUMMARY\)'
      setfiletype markdown
      return
    endif
    if line =~# 'EEB \(PACKAGE\|BUNDLE\|STANDARD EEB\) REPORT'
          \ || line =~# 'DELIVERABLE SUMMARY'
          \ || (line =~# '| INCIDENT' && line =~# 'SINCIDENT')
      setfiletype etrack-report
      return
    endif
  endfor
endfunction
