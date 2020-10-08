" Vim syntax file
" Language:         NetBackup legacy log file
" Maintainer:       Atul Das

" Based on legacy logging

if exists("b:current_syntax")
  finish
endif

"syn match   logBeginning    '^[0-9:\.]*\s\[[0-9\.]*\]\s<[0-9]*>' contains=log_time,log_thread

syn match   log_error       '\c.*\<\(FATAL\|ERROR\|ERRORS\|FAIL\|FAILED\|FAILURE\).*'
syn match   log_warning     '\c.*\<\(WARNING\|DELETE\|DELETING\|DELETED\|RETRY\|RETRYING\|Diagnostic\).*'
syn region  log_string      start=/'/ end=/'/ end=/$/ skip=/\\./
syn region  log_string      start=/"/ end=/"/ skip=/\\./
syn match   log_number      '0x[0-9a-fA-F]*\|\[<[0-9a-f]\+>\]\|\<\d[0-9a-fA-F]*'

syn match   log_date        '\(Jan\|Feb\|Mar\|Apr\|May\|Jun\|Jul\|Aug\|Sep\|Oct\|Nov\|Dec\) [ 0-9]\d *'
syn match   log_date        '\d\{4}-\d\d-\d\d'
syn match   log_date        '\d\+\/\d\+\/\d\+'

syn match   log_time        '\d\d:\d\d:\d\d\.\d\d\d\s*' nextgroup=log_thread

syn match   log_thread      '\[\d\+]\s*' nextgroup=log_rc,log_rc_warn,log_rc_error
syn match   log_thread      '\[\d\+\.\d\+]\s*' nextgroup=log_rc,log_rc_warn,log_rc_error

syn match   log_rc          '<\d>\s' nextgroup=log_fn
syn match   log_rc_warn     '<8>\s' contained nextgroup=log_fn
syn match   log_rc_error    '<16>\s' contained nextgroup=log_fn

syn match   log_fn          '\w*: ' contained
syn match   log_fn          '\w*\s\w*: ' contained
syn match   log_fn          '\w*::\w*: ' contained
syn match   log_fn          '\[\w*\.*\w*:.*\(\)\]' contained

syn match   log_fn_vxul     '\[\w*\.*\w*:.*\(\)\]'

hi def link log_date        Constant
hi def link log_time        Type
hi def link log_thread      Comment
hi def link log_fn          Function
hi def link log_fn_vxul     Function
hi def link log_rc          Type
hi def link log_rc_warn     WarningMsg
hi def link log_rc_error    Error
hi def link log_string      String
hi def link log_number      Number
hi def link log_error       ErrorMsg
hi def link log_warning     WarningMsg


let b:current_syntax = "nblog"
