#!/bin/sh
set -eu

PYTHON="${PYTHON:-python3}"

if ! "$PYTHON" -m pip --version >/dev/null 2>&1; then
    "$PYTHON" -m ensurepip --upgrade
fi

"$PYTHON" -m pip install --upgrade pip setuptools wheel
"$PYTHON" -m pip install -e .
