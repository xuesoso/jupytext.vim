" Minimal init file for headless test runs.
set nocompatible
filetype plugin on
syntax on
" Ensure the repo root is on runtimepath so plugin/jupytext.vim can be sourced.
let &runtimepath = getcwd() . ',' . &runtimepath
source plugin/jupytext.vim
