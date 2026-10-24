#!/usr/bin/env bash
# The Python utility validates the file and requires an explicit confirmation.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
exec "${PYTHON:-python3}" scripts/restore.py "$@"
