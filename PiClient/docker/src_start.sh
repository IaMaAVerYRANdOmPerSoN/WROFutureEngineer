#!/bin/sh
# Yes this file is basiclly just a wrapper for "python -m src", but we can extend it later and I like entrypoint okay!
set -e

exec python -m src "$@"
