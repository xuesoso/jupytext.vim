# jupytext.vim

[Vim][1]/[Neovim][2] plugin for editing [Jupyter notebook][3] (`.ipynb`) files through
[jupytext][4]. Open a notebook and it is converted on the fly to Markdown (or a
script) for editing; save the buffer and the `.ipynb` is rebuilt with its cell
outputs preserved.

> **This is an enhanced fork of [`goerz/jupytext.vim`][orig]** by Michael Goerz.
> It keeps the original workflow and configuration fully intact and adds
> non-blocking saves, a persistent conversion *daemon*, notebook-format
> auto-detection, and a fix for a data-loss footgun. Every change is additive
> and degrades gracefully to the original behavior. See
> [What's new in this fork](#whats-new-in-this-fork) and [Credits](#credits).

![jupytext.vim screenshot](https://gist.githubusercontent.com/goerz/884df0ffe9b017dbcd976011ad2c52d7/raw/f50439829092358acdc4a791c8e3fe4e780b0d89/screenshot_W8Yh8m.png "Screenshot of editing a notebook file in vim in md format")


## What's new in this fork

The upstream plugin shells out to the `jupytext` CLI *synchronously* on every
open and every save. Because `jupytext` is a Python program, ~95% of each call
is fixed Python/import startup (≈0.2s on a fast machine, often more on slower
disks, conda envs, or network filesystems) — paid on every `:w` regardless of
notebook size. This fork removes that latency from the editing loop.

* **⚡ Non-blocking saves** — `g:jupytext_async` (on by default). Your edits are
  written to the linked text file synchronously, and the `.ipynb` is rebuilt by
  a background job, so `:w` returns immediately instead of freezing the UI. The
  conversion is allowed to outlive `:wq`, rapid saves are collapsed into a
  single re-run, and failures are reported via `:messages`.

* **🚀 Persistent conversion daemon** — `g:jupytext_daemon` (on by default,
  **Neovim only**). A helper process imports `jupytext` once and converts on
  demand, turning the per-call ~0.2s startup into a one-time cost. Opening and
  saving notebooks drop to a few milliseconds. If no suitable Python is found —
  or if `g:jupytext_command` is set to something other than `jupytext` (e.g.
  `notedown`) — it transparently falls back to the CLI, so correctness never
  depends on it. In classic Vim, conversions use the CLI (asynchronously on
  save, per above).

* **🧭 Respects a notebook's own format** — `g:jupytext_respect_metadata` (on by
  default). A notebook paired/configured for, say, `py:percent` now opens in
  that format instead of being forced to the global `g:jupytext_fmt`.

* **🛟 No more accidental notebook clobbering** — if a notebook can't be
  converted on open (e.g. `jupytext` not installed, an invalid notebook, or a
  bad `g:jupytext_fmt`), the buffer now shows the **raw notebook JSON,
  read-only**, with a clear message — instead of leaving an empty, writable
  buffer whose next `:w` would silently overwrite your `.ipynb` with nothing. A
  preflight check also reports a missing `jupytext` up front.

* **🤫 Silent on success, loud on failure** — successful background saves stay
  quiet; only real conversion errors surface (via `:messages`).

* **🧹 Internals** — the async path uses argument lists, and the CLI fallback
  shell-escapes its arguments and uses the platform's null device (so a command
  path with spaces and Windows `cmd.exe` both work); plus assorted dead-code
  cleanup and unit/integration tests under `test/`.

All new behavior is controlled by the settings in
[Configuration](#configuration); set any of the new options to `0` to get the
original behavior back.


## Requirements

* The [`jupytext`][4] CLI: `pip install jupytext`.
* **Async saves** require Vim 8+ or Neovim (any build with `+job` support). On
  older builds the plugin falls back to the original blocking save.
* **The conversion daemon** requires **Neovim** (it uses a synchronous
  request/response over the job channel via `vim.wait()`), plus a Python in
  which `import jupytext` succeeds. Classic Vim works fully without the daemon.


## Installation

It's a single plugin — this one repository. (It happens to contain two files,
`plugin/jupytext.vim` and the daemon helper `plugin/jupytext_server.py`, which
`jupytext.vim` locates next to itself; a plugin manager installs both for you.)

**With a plugin manager** (recommended), point it at this repository, e.g. with
[vim-plug][vimplug]:

```vim
Plug 'xuesoso/jupytext.vim'
```

or [lazy.nvim][lazy]:

```lua
{ 'xuesoso/jupytext.vim' }
```

**Manually**: copy *both* files into a `plugin/` directory on your
`runtimepath` (e.g. `~/.vim/plugin/` or `~/.config/nvim/plugin/`), keeping them
side by side, then restart the editor. See `:help add-plugin`,
`:help add-global-plugin`, and `:help runtimepath`.

If `jupytext` is not on your `$PATH`, point the plugin at it:

```vim
let g:jupytext_command = '/path/to/jupytext'
```


## Usage

When you open a Jupyter notebook (`*.ipynb`), it is automatically converted from
JSON to Markdown (or a script) through [`jupytext`][4] and loaded into the
buffer. Saving the buffer updates the original `.ipynb` with your changes.

In more detail, opening `notebook.ipynb` creates a linked text file
`notebook.md` or `notebook.py` (depending on `g:jupytext_fmt`), the result of:

    jupytext --to=md --output notebook.md notebook.ipynb

The contents of that file are loaded into the buffer instead of the original
`notebook.ipynb`. When you save, the buffer is written back to `notebook.md` and
the notebook is rebuilt with:

    jupytext --to=ipynb --from=md --update --output notebook.ipynb notebook.md

The `--update` flag preserves the outputs of any cell whose input is unchanged
(so your figures and results survive a round-trip). With this fork, that rebuild
happens through the daemon and/or in the background, so `:w` does not block.

On closing the buffer, a `notebook.md` that the plugin generated is deleted. If
`notebook.md` already existed when you opened `notebook.ipynb`, it is used as-is
and preserved when closing the buffer.


## Configuration

Override any of the defaults below by setting the corresponding variable in your
`~/.vimrc` / `init.vim`.

*   `let g:jupytext_enable = 1`

    Set to `0` to disable the automatic conversion of `ipynb` files (i.e.
    deactivate this plugin).

*   `let g:jupytext_command = 'jupytext'`

    The `jupytext` command to use. May be a full path to a specific executable
    not on your `$PATH`.

*   `let g:jupytext_fmt = 'md'`

    The default format to convert the `ipynb` data to. Any format `jupytext`
    accepts for `--to` (see `jupytext --help`), except `'notebook'`/`'ipynb'`.
    Overridden per-notebook when `g:jupytext_respect_metadata` is on and the
    notebook declares its own format.

*   `let g:jupytext_to_ipynb_opts = '--to=ipynb --update'`

    Command-line options for converting from `g:jupytext_fmt` back to the
    notebook format.

*   `let g:jupytext_async = 1` *(new)*

    Rebuild the `ipynb` in the background on save instead of blocking the editor
    until `jupytext` finishes. Edits are written to the linked text file
    (`notebook.md`/`.py`) synchronously and the `ipynb` is rebuilt by a detached
    job, so `:w` returns immediately even for large notebooks. Conversion
    failures are reported via `:messages`. Set to `0` for the original blocking
    behavior; it also falls back automatically on builds without job support.
    Used as the fallback whenever the daemon is unavailable.

*   `let g:jupytext_daemon = 1` *(new, Neovim only)*

    Run conversions through a persistent helper that imports `jupytext` once,
    instead of paying the ~0.2s Python startup on *every* open and save. With
    the daemon, opening and saving drop to a few milliseconds. If the daemon
    cannot start (no usable Python, `jupytext` not importable, etc.) the plugin
    transparently falls back to the `jupytext` CLI, so correctness never depends
    on it. The daemon is only used when `g:jupytext_command` resolves to
    `jupytext`; with any other command (e.g. `notedown`) the CLI path is used.
    Set to `0` to disable. In classic Vim the CLI path is always used.

*   `let g:jupytext_python = ''` *(new)*

    The Python interpreter used to run the daemon. It must be one where
    `import jupytext` succeeds. When empty (default), it is auto-detected from
    the `jupytext` executable's shebang, falling back to `python3`.

*   `let g:jupytext_daemon_timeout = 5000` *(new)*

    Maximum time in milliseconds to wait for the conversion daemon handshake
    or a single conversion request. Increase this if the daemon times out on
    slow systems, conda environments, or very large notebooks.

*   `let g:jupytext_respect_metadata = 1` *(new)*

    When a notebook records its own jupytext text format (e.g. it is paired to
    `py:percent`), open it in that format instead of `g:jupytext_fmt`. Requires
    the daemon (Neovim). Set to `0` to always use `g:jupytext_fmt`.

*   `let g:jupytext_filetype_map = {}`

    A mapping of `g:jupytext_fmt` to the buffer filetype (`:help filetype`),
    which determines syntax highlighting. User-provided entries are merged with
    the plugin's built-in defaults, so you only need to specify the formats you
    want to override, e.g. to use `pandoc` instead of `markdown` for the `md`
    format:

        let g:jupytext_filetype_map = {'md': 'pandoc'}

*   `let g:jupytext_print_debug_msgs = 0`

    Set to `1` to print debug messages while running the plugin (view with
    `:messages`). Useful for confirming the daemon started
    (`DBG: daemon ready (...)`).


## Using notedown instead of jupytext

To use this plugin as a replacement for the [`ipynb_notedown.vim` plugin][5] via
[`notedown`][6]:

    let g:jupytext_command = 'notedown'
    let g:jupytext_fmt = 'markdown'
    let g:jupytext_to_ipynb_opts = '--to=notebook'

Conversions then go through the `notedown` CLI; the `jupytext`-specific daemon
and notebook-format auto-detection (`g:jupytext_respect_metadata`) do not apply.


## Credits

* Original plugin: **[`goerz/jupytext.vim`][orig]** by **Michael Goerz**
  (MIT-licensed), also published on [vim.org][vimorg]. This fork builds directly
  on that work.
* The [`jupytext`][4] conversion tool by **Marc Wouts** (`mwouts`).
* This fork: **[`xuesoso/jupytext.vim`][fork]**.

Released under the MIT License, the same as the original (see `LICENSE`).


[1]: http://www.vim.org
[2]: https://neovim.io
[3]: http://jupyter.org
[4]: https://github.com/mwouts/jupytext
[5]: https://github.com/goerz/ipynb_notedown.vim
[6]: https://github.com/aaren/notedown
[orig]: https://github.com/goerz/jupytext.vim
[fork]: https://github.com/xuesoso/jupytext.vim
[vimorg]: https://www.vim.org/scripts/script.php?script_id=5764
[vimplug]: https://github.com/junegunn/vim-plug
[lazy]: https://github.com/folke/lazy.nvim
