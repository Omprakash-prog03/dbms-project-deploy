"""Tests always use a freshly seeded, disposable database, never the running app's data."""
import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
_database_directory = tempfile.TemporaryDirectory(prefix='sims-tests-')
os.environ['DB_ENGINE'] = 'sqlite'
os.environ['SQLITE_PATH'] = os.path.join(_database_directory.name, 'tests.db')
from config import Config
Config.CSRF_ENABLED = False  # Dedicated security tests explicitly enable it.
from repositories.db_pool import db_pool

@pytest.fixture(scope='session', autouse=True)
def seeded_database():
    from db.seed import run_seed
    run_seed()
    yield
    _database_directory.cleanup()

@pytest.fixture(scope='session')
def db():
    return db_pool
