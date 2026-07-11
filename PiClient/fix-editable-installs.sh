#!/bin/bash
set -e

VENV="${1:-.venv}"
for pth in $VENV/lib/python*/site-packages/_editable_impl_*.pth; do
    [ -f "$pth" ] || continue
    sed -i 's|/src/piclient$|/src|' "$pth"
    echo "Fixed: $(basename "$pth")"
done