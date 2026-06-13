" Correctness tests: open/save round-trip with daemon and CLI fallback.
let g:jupytext_command = $PY39_JUPYTEXT
let g:jupytext_print_debug_msgs = 0

let s:results = []
let s:nb = $TEST_TMPDIR . '/correctness.ipynb'
let s:py = $PY39_PYTHON

function! s:assert(cond, msg) abort
    if a:cond
        call add(s:results, 'PASS: ' . a:msg)
    else
        call add(s:results, 'FAIL: ' . a:msg)
    endif
endfunction

" Create a notebook with outputs.
call system(s:py . ' ' . getcwd() . '/test/make_notebook.py ' . shellescape(s:nb) . ' 3 --outputs')

" ---------------------------------------------------------------------------
" 1) Daemon path (default): open, edit, save, verify ipynb updated.
" ---------------------------------------------------------------------------
execute 'edit ' . fnameescape(s:nb)
call s:assert(&filetype ==# 'markdown', 'daemon open: filetype is markdown')
call s:assert(search('^``` python', 'n') > 0 || search('cell 0', 'n') > 0, 'daemon open: buffer contains converted content')

" Append a markdown cell at the end.
call append(line('$'), ['', '# Test header added by correctness test', ''])
write
" Give async/daemon a moment to finish.
sleep 300m

" The linked text file should exist.
let s:md = fnamemodify(s:nb, ':r') . '.md'
call s:assert(filereadable(s:md), 'daemon save: linked md file exists')

" Verify the ipynb has the new cell by re-converting it and grepping.
let s:check = system(s:py . ' -c ' . shellescape('import json; nb=json.load(open(' . string(s:nb) . ')); print(sum(1 for c in nb["cells"] if "Test header" in "".join(c.get("source", []))))'))
call s:assert(s:check =~# '^1', 'daemon save: new cell found in ipynb (got: ' . s:check . ')')

" Outputs should be preserved (the notebook was created with outputs).
let s:outputs = system(s:py . ' -c ' . shellescape('import json; nb=json.load(open(' . string(s:nb) . ')); print(any(c.get("outputs") for c in nb["cells"]))'))
call s:assert(s:outputs =~# 'True', 'daemon save: cell outputs preserved')

bdelete!
if filereadable(s:md)
    call delete(s:md)
endif

" ---------------------------------------------------------------------------
" 2) CLI fallback: disable daemon, open, edit, save, verify.
" ---------------------------------------------------------------------------
let g:jupytext_daemon = 0
let g:jupytext_async = 0
" Recreate notebook to start clean.
call system(s:py . ' ' . getcwd() . '/test/make_notebook.py ' . shellescape(s:nb) . ' 3 --outputs')

execute 'edit ' . fnameescape(s:nb)
call s:assert(&filetype ==# 'markdown', 'cli open: filetype is markdown')

call append(line('$'), ['', '# CLI fallback header', ''])
write
sleep 100m

let s:check2 = system(s:py . ' -c ' . shellescape('import json; nb=json.load(open(' . string(s:nb) . ')); print(sum(1 for c in nb["cells"] if "CLI fallback header" in "".join(c.get("source", []))))'))
call s:assert(s:check2 =~# '^1', 'cli save: new cell found in ipynb (got: ' . s:check2 . ')')

bdelete!

" ---------------------------------------------------------------------------
" 3) Invalid format falls back to raw JSON read-only.
" ---------------------------------------------------------------------------
let g:jupytext_fmt = 'not_a_real_fmt'
call system(s:py . ' ' . getcwd() . '/test/make_notebook.py ' . shellescape(s:nb) . ' 2')
execute 'edit ' . fnameescape(s:nb)
call s:assert(&filetype ==# 'json', 'invalid fmt: filetype is json')
call s:assert(&modifiable == 0, 'invalid fmt: buffer is nomodifiable')
call s:assert(&buftype ==# 'nowrite', 'invalid fmt: buftype is nowrite')
call s:assert(search('"cells"', 'n') > 0, 'invalid fmt: raw JSON displayed')
bdelete!

" ---------------------------------------------------------------------------
" 4) User filetype map merge: override only md -> pandoc, others still work.
" ---------------------------------------------------------------------------
let g:jupytext_fmt = 'md'
let g:jupytext_filetype_map = {'md': 'pandoc'}
let g:jupytext_daemon = 1
call system(s:py . ' ' . getcwd() . '/test/make_notebook.py ' . shellescape(s:nb) . ' 2')
execute 'edit ' . fnameescape(s:nb)
call s:assert(&filetype ==# 'pandoc', 'filetype map merge: md maps to pandoc')
bdelete!

" Write results and exit.
call writefile(s:results, $TEST_TMPDIR . '/correctness.results')
if len(filter(copy(s:results), 'v:val =~# "^FAIL"')) > 0
    cquit 1
endif
quit
