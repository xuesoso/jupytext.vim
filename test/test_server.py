#!/usr/bin/env python3
"""Unit tests for plugin/jupytext_server.py.

Covers the targeted notebook-metadata extraction (_find_notebook_metadata /
_detect_fmt) and the CLI return-code handling (_run_cli). Run with:

    python3 -m unittest test.test_server      # from the repo root
    python3 test/test_server.py
"""
import importlib.util
import json
import os
import tempfile
import time
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_SERVER = os.path.join(_HERE, os.pardir, "plugin", "jupytext_server.py")
_spec = importlib.util.spec_from_file_location("jupytext_server", _SERVER)
srv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(srv)


def _cell(source="x = 1", with_meta=True, big_output=False):
    cell = {"cell_type": "code", "source": [source], "execution_count": 1}
    if with_meta:
        # A cell's own metadata: must never be mistaken for the notebook's.
        cell["metadata"] = {"collapsed": False, "tags": ["a", "b"]}
    else:
        cell["metadata"] = {}
    outputs = []
    if big_output:
        outputs.append({
            "output_type": "display_data",
            # Decoy text inside a JSON string is stored escaped, so it can never
            # match the unescaped "metadata" key the scanner searches for.
            "data": {"image/png": "QUJD" * 4000,
                     "text/plain": '{"metadata": {"jupytext": "decoy"}}'},
            "metadata": {},
        })
    cell["outputs"] = outputs
    return cell


def _nb(metadata, n_cells=3, big_output=False, metadata_first=False):
    cells = [_cell(big_output=big_output) for _ in range(n_cells)]
    nb = {}
    if metadata_first:
        nb["metadata"] = metadata
        nb["nbformat"] = 4
        nb["nbformat_minor"] = 5
        nb["cells"] = cells
    else:
        nb["cells"] = cells
        nb["metadata"] = metadata
        nb["nbformat"] = 4
        nb["nbformat_minor"] = 5
    return nb


def _dump(nb):
    return json.dumps(nb)


KERNELSPEC = {"name": "python3", "display_name": "Python 3"}


class FindMetadataTests(unittest.TestCase):
    def test_paired_formats(self):
        nb = _nb({"kernelspec": KERNELSPEC,
                  "jupytext": {"formats": "ipynb,py:percent"}})
        meta = srv._find_notebook_metadata(_dump(nb))
        self.assertIn("jupytext", meta)
        self.assertEqual(meta["jupytext"]["formats"], "ipynb,py:percent")

    def test_skips_cell_metadata(self):
        # Three cells each carry a "metadata" key before the notebook's own.
        nb = _nb({"kernelspec": KERNELSPEC,
                  "jupytext": {"formats": "ipynb,md"}}, n_cells=5)
        meta = srv._find_notebook_metadata(_dump(nb))
        self.assertIn("jupytext", meta)
        # Must NOT have returned a cell's metadata.
        self.assertNotIn("collapsed", meta)

    def test_metadata_first_layout(self):
        nb = _nb({"kernelspec": KERNELSPEC,
                  "jupytext": {"formats": "ipynb,R:spin"}}, metadata_first=True)
        meta = srv._find_notebook_metadata(_dump(nb))
        self.assertEqual(meta["jupytext"]["formats"], "ipynb,R:spin")

    def test_unpaired_returns_kernelspec_metadata(self):
        nb = _nb({"kernelspec": KERNELSPEC, "language_info": {"name": "python"}})
        meta = srv._find_notebook_metadata(_dump(nb))
        self.assertIn("kernelspec", meta)
        self.assertNotIn("jupytext", meta)

    def test_empty_metadata_fallback(self):
        # No marker keys anywhere -> falls back to a full parse.
        nb = _nb({})
        meta = srv._find_notebook_metadata(_dump(nb))
        self.assertEqual(meta, {})

    def test_decoy_in_output_string(self):
        nb = _nb({"kernelspec": KERNELSPEC,
                  "jupytext": {"formats": "ipynb,py:light"}},
                 n_cells=4, big_output=True)
        meta = srv._find_notebook_metadata(_dump(nb))
        self.assertEqual(meta["jupytext"]["formats"], "ipynb,py:light")

    def test_malformed_json(self):
        self.assertIsNone(srv._find_notebook_metadata('{"cells": [oops'))

    def test_not_an_object(self):
        self.assertIsNone(srv._find_notebook_metadata("[1, 2, 3]"))


class DetectFmtTests(unittest.TestCase):
    def _write_nb(self, nb):
        fd, path = tempfile.mkstemp(suffix=".ipynb")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(_dump(nb))
        self.addCleanup(os.remove, path)
        return path

    def test_formats(self):
        path = self._write_nb(_nb({"jupytext": {"formats": "ipynb,py:percent"}}))
        self.assertEqual(srv._detect_fmt(path), "py:percent")

    def test_formats_with_path_prefix(self):
        path = self._write_nb(
            _nb({"jupytext": {"formats": "notebooks//ipynb,scripts//py:percent"}}))
        self.assertEqual(srv._detect_fmt(path), "scripts//py:percent")

    def test_only_ipynb_format(self):
        path = self._write_nb(_nb({"jupytext": {"formats": "ipynb"}}))
        self.assertIsNone(srv._detect_fmt(path))

    def test_text_representation(self):
        path = self._write_nb(_nb({"jupytext": {"text_representation": {
            "extension": ".py", "format_name": "percent"}}}))
        self.assertEqual(srv._detect_fmt(path), "py:percent")

    def test_text_representation_ext_only(self):
        path = self._write_nb(_nb({"jupytext": {"text_representation": {
            "extension": ".md"}}}))
        self.assertEqual(srv._detect_fmt(path), "md")

    def test_unpaired_returns_none(self):
        path = self._write_nb(_nb({"kernelspec": KERNELSPEC}))
        self.assertIsNone(srv._detect_fmt(path))

    def test_missing_file(self):
        self.assertIsNone(srv._detect_fmt("/no/such/notebook.ipynb"))


class RunCliTests(unittest.TestCase):
    def test_returns_nonzero_is_failure(self):
        code, _ = srv._run_cli(lambda a: 1, ["--to=ipynb"])
        self.assertNotEqual(code, 0)

    def test_returns_none_is_success(self):
        code, _ = srv._run_cli(lambda a: None, [])
        self.assertEqual(code, 0)

    def test_systemexit_int(self):
        def boom(a):
            raise SystemExit(2)
        code, _ = srv._run_cli(boom, [])
        self.assertEqual(code, 2)

    def test_systemexit_string_normalized(self):
        def boom(a):
            raise SystemExit("bad format")
        code, _ = srv._run_cli(boom, [])
        self.assertEqual(code, 1)

    def test_captures_output(self):
        def chatty(a):
            print("hello stdout")
            return 0
        code, out = srv._run_cli(chatty, [])
        self.assertEqual(code, 0)
        self.assertIn("hello stdout", out)


class PerformanceTests(unittest.TestCase):
    def test_correct_and_not_slower_on_large_notebook(self):
        # ~2000 cells each with a large base64 output -> a heavy full parse.
        nb = _nb({"kernelspec": KERNELSPEC,
                  "jupytext": {"formats": "ipynb,py:percent"}},
                 n_cells=2000, big_output=True)
        text = _dump(nb)
        self.assertGreater(len(text), 5_000_000)  # multi-MB notebook

        t0 = time.perf_counter()
        meta = srv._find_notebook_metadata(text)
        t_scan = time.perf_counter() - t0

        t0 = time.perf_counter()
        full = json.loads(text)["metadata"]
        t_full = time.perf_counter() - t0

        # Correctness: same answer as the full parse.
        self.assertEqual(meta.get("jupytext"), full.get("jupytext"))
        # Performance: the targeted scan must not be dramatically slower than a
        # full parse (it should usually be faster). Generous bound to avoid
        # flakiness on loaded CI machines.
        self.assertLess(t_scan, t_full * 3 + 0.05,
                        "scan=%.4fs full=%.4fs" % (t_scan, t_full))
        print("\n[perf] large notebook (%.1f MB): scan=%.1fms full-parse=%.1fms"
              % (len(text) / 1e6, t_scan * 1e3, t_full * 1e3))


if __name__ == "__main__":
    unittest.main(verbosity=2)
