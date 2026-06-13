#!/usr/bin/env python
"""Persistent jupytext conversion server for jupytext.vim.

The plugin spawns one of these per editor session and talks to it over
stdin/stdout using newline-delimited JSON. Keeping jupytext imported once turns
the ~180 ms per-call Python/import cost into a one-time startup cost, so opens
and saves drop from ~200 ms to a few milliseconds.

Protocol (one JSON object per line, request -> response):

    -> {"id": 1, "op": "to_text",  "args": ["--to=md", "--output=nb.md", "nb.ipynb"]}
    <- {"id": 1, "ok": true}

    -> {"id": 2, "op": "to_ipynb", "args": ["--from=md", "--to=ipynb", "--update", "nb.md"]}
    <- {"id": 2, "ok": true}

    -> {"id": 3, "op": "detect",   "input": "nb.ipynb"}
    <- {"id": 3, "ok": true, "fmt": "py:percent"}   # or "fmt": null when unpaired

On startup the server emits one unsolicited handshake line:

    <- {"id": null, "ready": true, "ok": true}          # jupytext imported fine
    <- {"id": null, "ok": false, "fatal": true, ...}    # jupytext not importable

`args` is the exact jupytext CLI argument vector; the server dispatches it to
jupytext's own in-process CLI entry point, so behavior (including `--update`
output preservation) matches the command line exactly. The client is expected
to fall back to invoking the `jupytext` CLI directly if this server cannot be
started or reports a fatal error.
"""
import io
import json
import sys
from contextlib import redirect_stderr, redirect_stdout


def _write(obj):
    # stdout is the protocol channel: only ever JSON lines go here.
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def _find_notebook_metadata(text):
    """Return the notebook's top-level ``metadata`` object, or None.

    A full ``json.load`` of a large notebook builds Python objects for every
    cell and output (base64 images, long result arrays) -- the dominant cost on
    open, paid only to read a tiny ``metadata`` block. Instead, locate each
    ``"metadata"`` key with the C-level ``str.find`` and decode only the small
    object that follows it, returning the one that carries notebook-level
    metadata (it has a ``jupytext``/``kernelspec``/``language_info`` entry; a
    cell's metadata does not). Falls back to a full parse for unusual layouts.

    Decoy ``"metadata":`` text inside a cell output cannot cause a false match:
    such a decode either fails or yields a dict lacking the marker keys, so it
    is ignored.
    """
    decoder = json.JSONDecoder()
    needle = '"metadata"'
    nlen = len(needle)
    n = len(text)
    best = None
    pos = text.find(needle)
    while pos != -1:
        j = pos + nlen
        while j < n and text[j] in " \t\r\n":
            j += 1
        if j < n and text[j] == ":":
            j += 1
            while j < n and text[j] in " \t\r\n":
                j += 1
            try:
                val, _ = decoder.raw_decode(text, j)
            except ValueError:
                val = None
            if isinstance(val, dict):
                if "jupytext" in val:
                    return val  # definitive: this is the notebook metadata
                if best is None and ("kernelspec" in val or "language_info" in val):
                    best = val
        pos = text.find(needle, pos + nlen)
    if best is not None:
        return best
    # Fallback: a full parse handles notebooks whose top-level metadata carries
    # none of the marker keys, or an unusual key layout.
    try:
        obj = json.loads(text)
    except Exception:
        return None
    return obj.get("metadata") if isinstance(obj, dict) else None


def _detect_fmt(path):
    """Return the text format a notebook is paired/configured for, or None.

    Reads metadata.jupytext (no jupytext import needed). See
    _find_notebook_metadata for how this stays cheap on large notebooks.
    """
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except Exception:
        return None
    jt = (_find_notebook_metadata(text) or {}).get("jupytext") or {}
    formats = jt.get("formats")
    if isinstance(formats, str):
        for part in formats.split(","):
            part = part.strip()
            if part and part != "ipynb" and not part.endswith("ipynb"):
                return part
    tr = jt.get("text_representation") or {}
    ext = (tr.get("extension") or "").lstrip(".")
    name = tr.get("format_name")
    if ext and name:
        return ext + ":" + name
    if ext:
        return ext
    return None


def _run_cli(jcli, args):
    """Invoke jupytext's CLI in-process, capturing any stray output.

    jupytext's entry point signals failure two ways: it may raise SystemExit
    (e.g. argparse errors) or simply *return* a non-zero exit code. We must
    honor both -- a handled error that only returns non-zero would otherwise be
    reported to the client as success and the stale ipynb treated as saved.
    """
    buf = io.StringIO()
    code = 0
    with redirect_stdout(buf), redirect_stderr(buf):
        try:
            code = jcli(args) or 0
        except SystemExit as exc:  # the CLI exits on both success and error
            code = exc.code or 0
    # Normalize a non-int code (e.g. SystemExit with a string message) to 1.
    if not isinstance(code, int):
        code = 1
    return code, buf.getvalue()


def main():
    try:
        from jupytext.cli import jupytext as jcli
    except Exception as exc:  # noqa: BLE001 - report any import failure to client
        _write({"id": None, "ok": False, "fatal": True,
                "error": "cannot import jupytext: %s" % exc})
        return

    # Quiet jupytext's own logging so it never competes for the stdout channel.
    try:
        import logging
        logging.getLogger("jupytext").setLevel(logging.ERROR)
    except Exception:
        pass

    _write({"id": None, "ready": True, "ok": True})

    while True:
        line = sys.stdin.readline()
        if not line:  # editor closed the pipe (e.g. on exit)
            break
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception:
            continue

        rid = req.get("id")
        op = req.get("op")
        resp = {"id": rid, "ok": False}
        try:
            if op == "detect":
                resp["ok"] = True
                resp["fmt"] = _detect_fmt(req.get("input", ""))
            elif op in ("to_text", "to_ipynb"):
                code, out = _run_cli(jcli, req.get("args", []))
                resp["ok"] = code == 0
                if code != 0:
                    resp["error"] = out.strip()[-800:] or ("exit %s" % code)
            else:
                resp["error"] = "unknown op: %s" % op
        except Exception as exc:  # noqa: BLE001 - never let one request kill the server
            resp["ok"] = False
            resp["error"] = "%s" % exc
        _write(resp)


if __name__ == "__main__":
    main()
