" Define command for vertical split
command! -nargs=* Vncmd call s:ExecuteCommand('vnew', <f-args>)

" Define command for horizontal split
command! -nargs=* Ncmd call s:ExecuteCommand('new', <f-args>)

" Function to execute the commands
function! s:ExecuteCommand(window_type, ...)
    " Get the arguments
    let l:args = a:000

    " Check if we have at least one argument
    if len(l:args) == 0
        echo "Usage: vncmd <cmd> [args...]"
        return
    endif

    " Get the window type
    let l:window_type = a:window_type

    " Validate window type
    if l:window_type != 'vnew' && l:window_type != 'new'
        echo "Error: Invalid window type. Use 'vnew' or 'new'."
        return
    endif

    " Make a copy of the args list to avoid modifying the original
    let l:args_copy = copy(l:args)

    " Get the command and arguments
    let l:cmd = remove(l:args_copy, 0)
    let l:cmd_args = join(l:args_copy, ' ')

    " Build the command to execute silently
    let l:silent_cmd = ' ' . l:cmd . ' ' .  l:cmd_args

    " Execute the command in a vertical split and read its output
    " Open a new window based on the specified type
    execute l:window_type

    execute 'read !' .  l:silent_cmd
endfunction

