#!/bin/sh
set -eu

PROJECT_ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
export ORTIE_BIN="${ORTIE_BIN:-$HOME/.local/bin/ortie}"
export PATH="$HOME/.local/bin:$PATH"

exec python3 "$PROJECT_ROOT/scripts/viaplay_code.py" --json
