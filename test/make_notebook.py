#!/usr/bin/env python3
"""Helper to create synthetic Jupyter notebooks for testing."""
import json
import sys


def make_notebook(path, num_cells=3, with_outputs=False):
    cells = []
    for i in range(num_cells):
        cell = {
            "cell_type": "code",
            "execution_count": i + 1 if with_outputs else None,
            "id": "cell-%d" % i,
            "metadata": {},
            "outputs": [],
            "source": [f"print('cell {i}')\n"],
        }
        if with_outputs:
            cell["outputs"] = [{
                "output_type": "stream",
                "name": "stdout",
                "text": [f"cell {i}\n"],
            }]
        cells.append(cell)
    nb = {
        "cells": cells,
        "metadata": {
            "kernelspec": {
                "display_name": "python3",
                "language": "python",
                "name": "python3",
            }
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(nb, f)


if __name__ == "__main__":
    make_notebook(
        sys.argv[1],
        int(sys.argv[2]) if len(sys.argv) > 2 else 3,
        "--outputs" in sys.argv,
    )
