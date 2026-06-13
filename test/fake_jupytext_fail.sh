#!/usr/bin/env bash
# Fake jupytext that simulates a partial conversion failure: it writes the
# requested --output file and then exits with an error. Used by data-loss tests
# to verify the plugin cleans up the temporary file it created.
output=""
for arg in "$@"; do
    case "$arg" in
        --output=*)
            output="${arg#--output=}"
            ;;
    esac
done

if [[ -n "$output" ]]; then
    echo "partial conversion" > "$output"
fi

echo "jupytext fake error" >&2
exit 1
