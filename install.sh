#!/bin/sh
set -eu

# Allow user to override the Python interpreter. If PYTHON is a version like "3.9"
# it will be normalized to "python3.9". If PYTHON is a path or starts with
# "python" it will be used as-is.
RAW_PYTHON="${PYTHON:-}"
if [ -n "$RAW_PYTHON" ]; then
    case "$RAW_PYTHON" in
        [0-9]* )
            PYTHON="python$RAW_PYTHON"
            ;;
        *)
            PYTHON="$RAW_PYTHON"
            ;;
    esac
else
    PYTHON="python3"
fi

# Ensure the interpreter exists
if ! command -v "$PYTHON" >/dev/null 2>&1; then
    echo "error: specified Python interpreter '$PYTHON' not found" >&2
    exit 1
fi

if ! "$PYTHON" -m pip --version >/dev/null 2>&1; then
    "$PYTHON" -m ensurepip --upgrade
fi

"$PYTHON" -m pip install --upgrade pip setuptools wheel
"$PYTHON" -m pip install -e .
