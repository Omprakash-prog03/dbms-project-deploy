import os
import secrets
from datetime import timedelta
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(Path(os.getenv('HOGWARDS_ENV_FILE', BASE_DIR / '.env')))

class Config:
    PORTAL_NAME = "Hogwards Student Management System"
    PORTAL_SHORT_NAME = "Hogwards"
    PORTAL_DESCRIPTOR = "Student Management System"
    APP_ENV = os.getenv('APP_ENV', 'development').lower()
    # Production must never silently replace its signing key on a restart.
    SECRET_KEY = os.getenv('SECRET_KEY') or (None if APP_ENV == 'production' else secrets.token_hex(32))
    RATELIMIT_ENABLED = APP_ENV == 'production'
    TRUSTED_PROXY_HOPS = int(os.getenv('TRUSTED_PROXY_HOPS', '0'))
    DB_ENGINE = os.getenv('DB_ENGINE', 'auto').lower()
    SQLITE_PATH = str((BASE_DIR / os.getenv('SQLITE_PATH', 'sims_embedded.db')).resolve())
    DB_HOST = os.getenv('DB_HOST', '127.0.0.1')
    DB_PORT = int(os.getenv('DB_PORT', 3306))
    DB_USER = os.getenv('DB_USER', 'root')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '')
    DB_NAME = os.getenv('DB_NAME', 'sims_db')
    DB_POOL_NAME = os.getenv('DB_POOL_NAME', 'sims_pool')
    DB_POOL_SIZE = int(os.getenv('DB_POOL_SIZE', 10))
    DEBUG = False
    PORT = int(os.getenv('PORT', 5000))
    # HTTPS embedded previews need a partitioned third-party cookie. CSRF stays on.
    EMBEDDED_PREVIEW = os.getenv('EMBEDDED_PREVIEW', 'false').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'None' if EMBEDDED_PREVIEW else 'Lax'
    SESSION_COOKIE_PARTITIONED = EMBEDDED_PREVIEW
    SESSION_COOKIE_SECURE = EMBEDDED_PREVIEW or os.getenv('COOKIE_SECURE', 'false').lower() == 'true'
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    MAX_CONTENT_LENGTH = 1024 * 1024
    CSRF_ENABLED = True
    DEMO_MODE = os.getenv('DEMO_MODE', 'false').lower() == 'true'
