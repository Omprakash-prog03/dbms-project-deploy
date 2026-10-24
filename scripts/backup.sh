#!/usr/bin/env bash
# Delegate to the configured-engine, transaction-safe backup utility.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
exec "${PYTHON:-python3}" scripts/backup.py
