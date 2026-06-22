#!/bin/bash
set -e

VENV="${1:-.venv}"
SITE_PKGS="$VENV/lib/python"*"/site-packages"

for pth in "$SITE_PKGS"/_editable_impl_piclient*.pth; do
    [ -f "$pth" ] || continue
    sed -i 's|/src/piclient$|/src|' "$pth"
    echo "Fixed: $(basename "$pth")"
done