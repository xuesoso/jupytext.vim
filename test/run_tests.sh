#!/usr/bin/env bash
# Test runner for jupytext.vim.
#
# Requires:
#   - nvim in $PATH
#   - $HOME/py39_env/bin/jupytext and $HOME/py39_env/bin/python3
set -euo pipefail

cd "$(dirname "$0")/.."

export PY39_JUPYTEXT="${HOME}/py39_env/bin/jupytext"
export PY39_PYTHON="${HOME}/py39_env/bin/python3"

if [[ ! -x "$PY39_JUPYTEXT" ]]; then
    echo "ERROR: $PY39_JUPYTEXT not found or not executable" >&2
    exit 1
fi

TEST_TMPDIR="$(mktemp -d)"
export TEST_TMPDIR
trap 'rm -rf "$TEST_TMPDIR"' EXIT

echo "Running jupytext.vim tests"
echo "  jupytext: $PY39_JUPYTEXT"
echo "  python:   $PY39_PYTHON"
echo "  tmpdir:   $TEST_TMPDIR"
echo

run_test() {
    local name="$1"
    local script="test/${name}.vim"
    local result_file="$TEST_TMPDIR/${name}.results"
    echo "==> $name"
    if nvim --headless -u test/minimal.vim -S "$script"; then
        if [[ -f "$result_file" ]]; then
            cat "$result_file"
        fi
        echo "    $name PASSED"
    else
        echo "    $name FAILED (exit $?)"
        if [[ -f "$result_file" ]]; then
            cat "$result_file"
        fi
        return 1
    fi
    echo
}

run_test test_correctness
run_test test_data_loss
run_test test_performance

echo "==> test_server (python unit tests)"
"$PY39_PYTHON" -m unittest -v test.test_server
echo "    test_server PASSED"
echo

echo "All tests passed."
