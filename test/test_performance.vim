" Performance tests: measure open and save latency with/without daemon.
let g:jupytext_command = $PY39_JUPYTEXT
let g:jupytext_print_debug_msgs = 0

let s:results = []
let s:nb = $TEST_TMPDIR . '/perf.ipynb'
let s:py = $PY39_PYTHON
let s:cells = 100

function! s:measure(msg, cmd) abort
    let l:start = reltime()
    execute a:cmd
    let l:elapsed = reltimefloat(reltime(l:start)) * 1000
    call add(s:results, printf('PERF: %s = %.2f ms', a:msg, l:elapsed))
    return l:elapsed
endfunction

" Create a notebook with many cells.
call system(s:py . ' ' . getcwd() . '/test/make_notebook.py ' . shellescape(s:nb) . ' ' . s:cells . ' --outputs')

" ---------------------------------------------------------------------------
" 1) With daemon (default).
" ---------------------------------------------------------------------------
let g:jupytext_daemon = 1
let g:jupytext_async = 1
let s:t_open_daemon = s:measure('daemon open ' . s:cells . ' cells', 'edit ' . fnameescape(s:nb))
call append(line('$'), ['', '# Performance test addition', ''])
let s:t_save_daemon = s:measure('daemon save ' . s:cells . ' cells', 'write')
sleep 300m
bdelete!

" ---------------------------------------------------------------------------
" 2) Without daemon, sync CLI.
" ---------------------------------------------------------------------------
let g:jupytext_daemon = 0
let g:jupytext_async = 0
" Recreate notebook to keep comparison fair.
call system(s:py . ' ' . getcwd() . '/test/make_notebook.py ' . shellescape(s:nb) . ' ' . s:cells . ' --outputs')
let s:t_open_cli = s:measure('cli open ' . s:cells . ' cells', 'edit ' . fnameescape(s:nb))
call append(line('$'), ['', '# Performance test addition', ''])
let s:t_save_cli = s:measure('cli save ' . s:cells . ' cells', 'write')
bdelete!

" Sanity: daemon should be faster for the 100-cell notebook.
if s:t_open_cli > 0 && s:t_open_daemon > 0
    call add(s:results, printf('PERF: open speedup vs CLI = %.2fx', s:t_open_cli / s:t_open_daemon))
endif
if s:t_save_cli > 0 && s:t_save_daemon > 0
    call add(s:results, printf('PERF: save speedup vs CLI = %.2fx', s:t_save_cli / s:t_save_daemon))
endif

call writefile(s:results, $TEST_TMPDIR . '/performance.results')
quit
