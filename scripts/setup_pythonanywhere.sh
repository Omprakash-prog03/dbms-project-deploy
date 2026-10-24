#!/usr/bin/env bash
# Run only in your own PythonAnywhere Bash console after cloning this branch.
# This configures files; the Web tab is still required to publish the application.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ -n "${PYTHON_BIN:-}" ]]; then
  PYTHON="$PYTHON_BIN"
else
  PYTHON=""
  for candidate in python3.13 python3.12 python3.11; do
    if command -v "$candidate" >/dev/null 2>&1; then PYTHON="$candidate"; break; fi
  done
fi
if [[ -z "$PYTHON" ]]; then echo 'Python 3.11+ is required.' >&2; exit 1; fi
if [[ ! -d .venv ]]; then "$PYTHON" -m venv .venv; fi
.venv/bin/python -m pip install --no-cache-dir -r requirements-runtime.txt
if [[ ! -f .env ]]; then
  .venv/bin/python scripts/init_production.py --proxy-hops 1
else
  echo 'Existing configuration preserved; verifying it without changing records or passwords.'
fi
.venv/bin/python scripts/check_production.py
.venv/bin/python - <<'PY'
from pathlib import Path
import sys
root = Path.cwd()
print('\nNEXT: Web → Add a new web app → Manual configuration.')
print(f'Select Python {sys.version_info.major}.{sys.version_info.minor}.')
print(f'Virtualenv: {root / ".venv"}')
print(f'Source code / Working directory: {root}')
print(f'Static mapping: /static/ → {root / "static"}')
print('Enable Force HTTPS, then replace the Web-tab WSGI file with:\n')
print('import sys')
print(f'sys.path.insert(0, {str(root)!r})')
print('from wsgi import application')
print('\nClick Reload in the Web tab. /healthz should return status: ok.')
print('Do not map the project root, instance, .env, or backups as static files.')
print('Renew the free web app before its monthly expiry and download regular private backups.')
PY
