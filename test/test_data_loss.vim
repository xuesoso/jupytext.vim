" Data-loss tests: verify the original .ipynb is never overwritten with empty
" or partial content when jupytext is unavailable or conversion fails.
let g:jupytext_command = $PY39_JUPYTEXT
let g:jupytext_print_debug_msgs = 0

let s:results = []
let s:nb = $TEST_TMPDIR . '/data_loss.ipynb'
let s:py = $PY39_PYTHON

function! s:assert(cond, msg) abort
    if a:cond
        call add(s:results, 'PASS: ' . a:msg)
    else
        call add(s:results, 'FAIL: ' . a:msg)
    endif
endfunction

" Create a notebook and record its original cell count.
call system(s:py . ' ' . getcwd() . '/test/make_notebook.py ' . shellescape(s:nb) . ' 5 --outputs')
let s:orig_cells = system(s:py . ' -c ' . shellescape('import json; nb=json.load(open(' . string(s:nb) . ')); print(len(nb["cells"]))'))

" ---------------------------------------------------------------------------
" 1) jupytext missing: buffer becomes raw JSON read-only; :w cannot clobber.
" ---------------------------------------------------------------------------
let g:jupytext_command = '/nonexistent/jupytext'
let g:jupytext_daemon = 0
let g:jupytext_async = 0
let g:jupytext_fmt = 'md'

execute 'edit ' . fnameescape(s:nb)
call s:assert(&filetype ==# 'json', 'missing jupytext: filetype is json')
call s:assert(&modifiable == 0, 'missing jupytext: buffer is nomodifiable')
call s:assert(&buftype ==# 'nowrite', 'missing jupytext: buftype is nowrite')

" Attempting to write a nomodifiable buffer should fail; even if it somehow
" succeeded, the original file must remain intact.
try
    write
    call s:assert(0, 'missing jupytext: write should have failed')
catch
    call s:assert(1, 'missing jupytext: write was rejected')
endtry

let s:after_cells = system(s:py . ' -c ' . shellescape('import json; nb=json.load(open(' . string(s:nb) . ')); print(len(nb["cells"]))'))
call s:assert(s:after_cells ==# s:orig_cells, 'missing jupytext: original cell count preserved')

bdelete!

" ---------------------------------------------------------------------------
" 2) Invalid format: same read-only safety.
" ---------------------------------------------------------------------------
let g:jupytext_command = $PY39_JUPYTEXT
let g:jupytext_fmt = 'totally_invalid_format_xyz'
execute 'edit ' . fnameescape(s:nb)
call s:assert(&filetype ==# 'json', 'invalid format: filetype is json')
call s:assert(&modifiable == 0, 'invalid format: buffer is nomodifiable')

try
    write
    call s:assert(0, 'invalid format: write should have failed')
catch
    call s:assert(1, 'invalid format: write was rejected')
endtry

let s:after_cells2 = system(s:py . ' -c ' . shellescape('import json; nb=json.load(open(' . string(s:nb) . ')); print(len(nb["cells"]))'))
call s:assert(s:after_cells2 ==# s:orig_cells, 'invalid format: original cell count preserved')

bdelete!

" ---------------------------------------------------------------------------
" 3) Partial conversion failure should clean up the temp file.
" ---------------------------------------------------------------------------
let g:jupytext_command = getcwd() . '/test/fake_jupytext_fail.sh'
let g:jupytext_daemon = 0
let g:jupytext_async = 0
let g:jupytext_fmt = 'md'
let g:jupytext_to_ipynb_opts = '--to=ipynb --update'
call system(s:py . ' ' . getcwd() . '/test/make_notebook.py ' . shellescape(s:nb) . ' 2')
let s:md = fnamemodify(s:nb, ':r') . '.md'
execute 'edit ' . fnameescape(s:nb)
call s:assert(&filetype ==# 'json', 'fake fail: filetype is json')
call s:assert(&modifiable == 0, 'fake fail: buffer is nomodifiable')
call s:assert(!filereadable(s:md), 'fake fail: partial temp file removed')

bdelete!

" Write results and exit.
call writefile(s:results, $TEST_TMPDIR . '/data_loss.results')
if len(filter(copy(s:results), 'v:val =~# "^FAIL"')) > 0
    cquit 1
endif
quit
