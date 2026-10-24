"""Production WSGI entry point (PythonAnywhere or another Python WSGI host)."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
configuration = Path(os.getenv('HOGWARDS_ENV_FILE', ROOT / '.env'))
if not configuration.is_file():
    raise RuntimeError('Initialize the private installation with scripts/init_production.py before publishing it.')
# Never run the public WSGI entry point with development security defaults.
os.environ['APP_ENV'] = 'production'
from app import app as application
