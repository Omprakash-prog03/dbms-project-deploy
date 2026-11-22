"""Tests for the Marvel & DC Universe module.

The dataset itself is built and verified by `scripts/build_universe_dataset.py`
(which is where row counts, foreign keys and duplicates are checked). These tests
cover the part the build script cannot: routing, permissions, the read-only
guarantee on the SQL gallery, and the behaviour when the dataset is not loaded.
"""
import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, 'scripts'))

from app import create_app                       # noqa: E402
from repositories import universe as repo        # noqa: E402
from repositories import owner as owner_guard    # noqa: E402

IMPORT_ERROR = None
try:                                             # the build script lives outside the app
    import build_universe_dataset  # noqa: E402
except Exception as exc:                         # pragma: no cover - import-time only
    build_universe_dataset = None
    IMPORT_ERROR = exc


@pytest.fixture(scope='module', autouse=True)
def universe_tables():
    """Load the demonstration dataset into the disposable test database.

    The suite runs against an empty temporary database, so without this every universe
    page would correctly render its "not loaded yet" state instead of being tested.
    Only the 14 `uni_` tables are created.
    """
    if build_universe_dataset is None:
        pytest.skip(f'build script not importable: {IMPORT_ERROR}')
    from repositories.db_pool import db_pool
    build_universe_dataset.OUT = build_universe_dataset.Path('/tmp/universe-test-artifacts')
    entities, indexes = build_universe_dataset.build()
    build_universe_dataset.load(entities, reset=True)
    yield
    for view in build_universe_dataset.VIEWS:
        try:
            db_pool.execute_dml(f'DROP VIEW IF EXISTS {view}')
        except Exception:
            pass
    for entity in reversed(build_universe_dataset.LOAD_ORDER):
        try:
            db_pool.execute_dml(
                f'DROP TABLE IF EXISTS {build_universe_dataset.TABLE_FOR[entity][0]}')
        except Exception:
            pass


@pytest.fixture(scope='module')
def app():
    return create_app({'TESTING': True, 'WTF_CSRF_ENABLED': False})


@pytest.fixture(scope='module')
def admin(app, db):
    """A real signed-in admin session, created through the login route itself."""
    import bcrypt
    # The seeded `admin` account is the supreme owner and is redirected to /supreme,
    # so make a plainly-scoped admin of our own for the ordinary-admin checks.
    hashed = bcrypt.hashpw(b'UniverseTest123', bcrypt.gensalt()).decode('utf-8')
    db.execute_dml("DELETE FROM app_user WHERE username = 'universe_admin'")
    db.execute_dml("INSERT INTO app_user (username, password_hash, role) "
                   "VALUES (?, ?, 'admin')", ('universe_admin', hashed))
    client = app.test_client()
    response = client.post('/api/auth/login',
                           json={'username': 'universe_admin',
                                 'password': 'UniverseTest123'})
    assert response.status_code == 200 and response.get_json()['success'], response.data
    return client


@pytest.fixture(scope='module')
def student(app, db):
    row = db.execute_query("SELECT student_id, user_id, username FROM app_user "
                           "WHERE role = 'student' ORDER BY user_id LIMIT 1", fetch='one')
    import bcrypt
    hashed = bcrypt.hashpw(b'UniverseTest123', bcrypt.gensalt()).decode('utf-8')
    db.execute_dml('UPDATE app_user SET password_hash = ? WHERE user_id = ?',
                   (hashed, row['user_id']))
    client = app.test_client()
    response = client.post('/api/auth/login',
                           json={'username': row['username'],
                                 'password': 'UniverseTest123'})
    assert response.status_code == 200 and response.get_json()['success'], response.data
    return client


# --- the dataset is present ---------------------------------------------------
def test_dataset_is_loaded(db):
    """The build script must have been run; an empty module would make the rest moot."""
    counts = repo.counts()
    assert counts, 'no uni_ tables found — run scripts/build_universe_dataset.py --reset'
    by_label = {row['table']: row['rows'] for row in counts}
    assert by_label['uni_universe'] == 2
    for table, rows in by_label.items():
        assert rows > 0, f'{table} is empty'


def test_every_gallery_query_runs():
    """A gallery query that raises is a broken demonstration, so all of them must run."""
    failures = []
    for index in range(len(repo.DEMO_QUERIES)):
        result = repo.run_demo(index)
        assert result is not None
        if not result['ok']:
            failures.append((index, result['title'], result['error']))
    assert not failures, failures


def test_gallery_rejects_writes(db):
    """The gallery is SELECT/WITH only; the guard is a regex in the repository."""
    assert repo.READ_ONLY.match('SELECT 1')
    assert repo.READ_ONLY.match('  with x as (select 1) select * from x')
    for statement in ('DELETE FROM uni_character', 'UPDATE uni_power SET power_level = 10',
                      'DROP TABLE uni_universe', 'INSERT INTO uni_team VALUES (1)'):
        assert not repo.READ_ONLY.match(statement), statement


# --- permissions --------------------------------------------------------------
def test_anonymous_is_sent_to_login(app):
    response = app.test_client().get('/universe/')
    assert response.status_code == 302
    assert '/login' in response.headers['Location']


def test_signed_in_user_can_browse(student):
    for path in ('/universe/', '/universe/characters', '/universe/teams',
                 '/universe/powers', '/universe/memberships', '/universe/screen',
                 '/universe/comics', '/universe/missions', '/universe/organizations',
                 '/universe/battles', '/universe/relationships'):
        assert student.get(path).status_code == 200, path


def test_sql_gallery_is_admin_only(student):
    assert student.get('/universe/sql').status_code == 403
    assert student.get('/universe/verify').status_code == 403
    response = student.post('/universe/compile', json={})
    assert response.status_code == 403


def test_admin_can_reach_every_page(admin):
    paths = ['/universe/', '/universe/characters', '/universe/characters/1',
             '/universe/teams', '/universe/teams/1', '/universe/powers',
             '/universe/memberships', '/universe/screen', '/universe/comics',
             '/universe/missions', '/universe/missions/1', '/universe/organizations',
             '/universe/battles', '/universe/battles/1', '/universe/relationships',
             '/universe/sql', '/universe/verify', '/universe/datasets/universe.xlsx']
    for path in paths:
        assert admin.get(path).status_code == 200, path


# --- detail pages -------------------------------------------------------------
def test_character_page_shows_its_mappings(admin):
    character = repo.character_detail(2)
    assert character['character']['alias'] == 'Captain America'
    assert character['powers'], 'Captain America should have mapped powers'
    assert character['teams'], 'Captain America should have a membership'
    page = admin.get('/universe/characters/2')
    assert b'Captain America' in page.data
    assert b'Powers and abilities' in page.data


def test_battle_page_lists_both_sides(admin):
    battle = repo.battle_detail(1)
    sides = {row['side'] for row in battle['roster']}
    assert len(sides) == 2, sides
    assert any(row['battle_result'] == 'Victorious' for row in battle['roster'])
    assert any(row['battle_result'] == 'Defeated' for row in battle['roster'])


def test_unknown_ids_are_404(admin):
    assert admin.get('/universe/characters/99999').status_code == 404
    assert admin.get('/universe/teams/99999').status_code == 404
    assert admin.get('/universe/battles/99999').status_code == 404


# --- dataset downloads --------------------------------------------------------
def test_downloads_stay_inside_the_dataset_directory(admin):
    assert admin.get('/universe/datasets/universe.xlsx').status_code == 200
    assert admin.get('/universe/datasets/csv/characters.csv').status_code == 200
    # traversal must not reach the application source
    for attempt in ('../app.py', '..%2Fapp.py', '../../config.py'):
        assert admin.get(f'/universe/datasets/{attempt}').status_code in (404, 308), attempt


# --- the empty-database path --------------------------------------------------
def test_missing_dataset_is_a_friendly_page(monkeypatch, admin):
    """A fresh deployment must explain itself, not raise a 500."""
    monkeypatch.setattr(repo, 'installed', lambda: False)
    response = admin.get('/universe/')
    assert response.status_code == 200
    assert b'build_universe_dataset.py' in response.data
