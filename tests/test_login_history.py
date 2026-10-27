"""The sign-in history: every login and logout, for every role, unchangeable."""
import bcrypt
import pytest

from app import create_app
from config import Config
from repositories import admin_sessions, login_history, owner, sqlconsole, staff_activity
from repositories.db_pool import db_pool

MASTER = 'supreme-master-key-9876'


@pytest.fixture(autouse=True)
def fresh_history(monkeypatch):
    """A clean, freshly guarded table for each test."""
    from repositories.owner import GUARD_TABLE, REQUEST_TABLE
    owner.ensure_schema()
    admin_sessions.ensure_schema()
    db_pool.execute_dml(f'DELETE FROM {REQUEST_TABLE}')
    db_pool.execute_dml(f'DELETE FROM {GUARD_TABLE}')
    db_pool.execute_dml(f'DELETE FROM {admin_sessions.TABLE}')
    db_pool.execute_dml("DELETE FROM app_user WHERE username IN "
                        "('om-2026', 'omprakash', 'deputy')")
    for trigger in ('trg_login_history_no_update', 'trg_login_history_no_delete'):
        db_pool.execute_dml(f'DROP TRIGGER IF EXISTS {trigger}')
    db_pool.execute_dml(f'DROP TABLE IF EXISTS {login_history.TABLE}')
    monkeypatch.setattr(login_history, '_ready', False)
    login_history.ensure_schema()
    yield
    # Leave the shared test database exactly as the rest of the suite expects it:
    # no master key (so the guard is open), no sessions, and no stray accounts.
    for account in ('om-2026', 'omprakash', 'deputy'):
        db_pool.execute_dml('DELETE FROM app_user WHERE username = %s', (account,))
        db_pool.execute_dml('DELETE FROM admin_session WHERE username = %s', (account,))
    for account in ('om-2026', 'omprakash', 'deputy'):
        db_pool.execute_dml('DELETE FROM app_user WHERE username = %s', (account,))
        db_pool.execute_dml('DELETE FROM admin_session WHERE username = %s', (account,))
    db_pool.execute_dml(f'DELETE FROM {GUARD_TABLE}')
    db_pool.execute_dml(f'DELETE FROM {REQUEST_TABLE}')
    login_history._ready = False
    staff_activity._ready = False


@pytest.fixture
def app():
    return create_app({'TESTING': True, 'CSRF_ENABLED': False, 'RATELIMIT_ENABLED': False})


def make_admin(username, password='deputy-pass-1'):
    digest = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    db_pool.execute_dml(
        "INSERT INTO app_user (username, password_hash, role) VALUES (%s, %s, 'admin')",
        (username, digest))
    return db_pool.execute_query('SELECT user_id FROM app_user WHERE username = %s',
                                 (username,), fetch='val')


def owner_client(app):
    client = app.test_client()
    with client.session_transaction() as session:
        session.update(user_id=99, username='om-2026', role='admin', access_approved=True,
                       supreme=True, owner_epoch=owner.epoch(),
                       admin_token_version=admin_sessions.version('om-2026'))
    return client


def entries(username=None):
    rows = login_history.recent(limit=200)
    if username:
        rows = [row for row in rows if row['username'] == username]
    return rows


# ---------------------------------------------------------------------------
# every role is written down
# ---------------------------------------------------------------------------
def test_an_administrator_sign_in_and_sign_out_are_recorded(app, monkeypatch):
    monkeypatch.setattr(Config, 'OTP_EXEMPT_ADMINS', 'omprakash')
    make_admin('omprakash', 'OmAdmin123')
    client = app.test_client()
    assert client.post('/api/auth/login', json={
        'username': 'omprakash', 'password': 'OmAdmin123'}).status_code == 200

    first = entries('omprakash')
    assert len(first) == 1
    assert first[0]['event'] == login_history.SIGNED_IN
    assert first[0]['role'] == 'admin'
    assert first[0]['at']  # a readable local time

    assert client.post('/logout').status_code == 302
    second = entries('omprakash')
    assert [row['event'] for row in second] == ['signed out', 'signed in']


def test_a_faculty_and_a_student_sign_in_are_recorded(app):
    faculty_username = db_pool.execute_query(
        "SELECT username FROM app_user WHERE role = 'faculty' LIMIT 1", fetch='val')
    student_username = db_pool.execute_query(
        "SELECT username FROM app_user WHERE role = 'student' LIMIT 1", fetch='val')
    assert faculty_username and student_username

    # Their passwords are set by the office; set one here so the login can happen.
    for username, secret in ((faculty_username, 'faculty-history-1'),
                             (student_username, 'student-history-1')):
        digest = bcrypt.hashpw(secret.encode(), bcrypt.gensalt()).decode()
        db_pool.execute_dml('UPDATE app_user SET password_hash = %s WHERE username = %s',
                            (digest, username))
        signed_in = app.test_client().post('/api/auth/login', json={
            'username': username, 'password': secret})
        assert signed_in.status_code == 200, signed_in.get_json()
        row = entries(username)[0]
        assert row['event'] == login_history.SIGNED_IN
        assert row['role'] in ('faculty', 'student')


def test_the_supreme_sign_in_is_recorded_as_supreme(app):
    make_admin('om-2026', 'Superadmin123')
    client = app.test_client()
    client.post('/supreme/login', data={'username': 'om-2026', 'password': 'Superadmin123'})
    row = entries('om-2026')[0]
    assert row['role'] == 'supreme'
    assert row['event'] == login_history.SIGNED_IN
    assert row['detail'] == 'at the supreme sign-in page'


def test_the_supreme_sign_out_is_recorded(app):
    make_admin('om-2026', 'Superadmin123')
    client = app.test_client()
    client.post('/supreme/login', data={'username': 'om-2026', 'password': 'Superadmin123'})
    client.post('/logout')
    assert [row['event'] for row in entries('om-2026')] == ['signed out', 'signed in']


# ---------------------------------------------------------------------------
# the supreme administrator ending someone else's session
# ---------------------------------------------------------------------------
def test_ending_one_session_says_who_did_it(app):
    make_admin('om-2026', 'Superadmin123')
    make_admin('deputy')
    owner.set_master_key(MASTER)
    owner_client(app).post('/owner/sign-out/deputy')
    row = entries('deputy')[0]
    assert row['event'] == login_history.SIGNED_OUT
    assert 'supreme administrator' in row['detail']


def test_signing_everyone_out_writes_one_line_per_live_administrator(app):
    make_admin('om-2026', 'Superadmin123')
    make_admin('deputy')
    mine = owner_client(app)
    admin_sessions.register('deputy', '10.0.0.9')
    admin_sessions.touch('deputy', '10.0.0.9')
    mine.post('/owner/lockdown', data={'master_key': MASTER})
    row = entries('deputy')[0]
    assert row['event'] == login_history.SIGNED_OUT
    assert 'sign out everyone else' in row['detail']


def test_removing_an_account_closes_its_history(app):
    make_admin('om-2026', 'Superadmin123')
    make_admin('deputy')
    owner.set_master_key(MASTER)
    owner_client(app).post('/owner/remove/deputy', data={'master_key': MASTER})
    row = entries('deputy')[0]
    assert row['event'] == login_history.SIGNED_OUT
    assert 'account removed' in row['detail']


# ---------------------------------------------------------------------------
# it cannot be altered
# ---------------------------------------------------------------------------
def test_the_database_refuses_to_change_history():
    login_history.record('deputy', 'admin', login_history.SIGNED_IN, '127.0.0.1')
    with pytest.raises(Exception):
        db_pool.execute_dml("UPDATE login_history SET username = 'someone-else'")
    with pytest.raises(Exception):
        db_pool.execute_dml("DELETE FROM login_history")
    assert entries('deputy')[0]['event'] == login_history.SIGNED_IN


def test_the_sql_console_refuses_to_write_to_history():
    for statement in (
        "UPDATE login_history SET username = 'x'",
        "DELETE FROM login_history",
        "INSERT INTO login_history (username, role, event, happened_at) VALUES ('x','admin','signed in','2026-01-01 00:00:00')",
    ):
        outcome = sqlconsole.run(statement, allow_full_write=True)
        assert outcome['ok'] is False, statement
        assert 'append-only' in outcome['error']
    # Reading is allowed.
    reading = sqlconsole.run('SELECT username, event FROM login_history')
    assert reading['ok'] is True


# ---------------------------------------------------------------------------
# the section on the dashboard
# ---------------------------------------------------------------------------
def test_the_dashboard_shows_the_history_with_times(app):
    make_admin('om-2026', 'Superadmin123')
    login_history.record('deputy', 'admin', login_history.SIGNED_IN, '10.0.0.7')
    login_history.record('student1', 'student', login_history.SIGNED_IN, '10.0.0.8')
    login_history.record('deputy', 'admin', login_history.SIGNED_OUT, '10.0.0.7',
                         'signed out from the portal')

    page = owner_client(app).get('/owner')
    assert page.status_code == 200
    body = page.get_data(as_text=True)
    assert 'Sign-in history' in body
    assert 'student1' in body
    assert 'signed out' in body
    assert '10.0.0.7' in body
    assert 'cannot be edited or deleted' in body
    assert login_history.time_label() in body
    assert entries()[0]['at'] != ''


def test_the_history_can_be_filtered(app):
    make_admin('om-2026', 'Superadmin123')
    login_history.record('deputy', 'admin', login_history.SIGNED_IN)
    login_history.record('student1', 'student', login_history.SIGNED_IN)
    login_history.record('deputy', 'admin', login_history.SIGNED_OUT)
    mine = owner_client(app)

    def section(body):
        return body[body.index('id="sign-in-history"'):body.index('Owner activity')]

    only_students = section(mine.get('/owner?role=student').get_data(as_text=True))
    assert 'student1' in only_students
    assert 'deputy' not in only_students

    only_out = section(mine.get('/owner?event=signed+out').get_data(as_text=True))
    assert 'signed out' in only_out
    assert 'student1' not in only_out

    by_name = section(mine.get('/owner?who=dep').get_data(as_text=True))
    assert 'deputy' in by_name
    assert 'student1' not in by_name


def test_only_the_supreme_administrator_sees_the_history(app):
    make_admin('om-2026', 'Superadmin123')
    make_admin('deputy')
    login_history.record('student1', 'student', login_history.SIGNED_IN)
    assert owner_client(app).get('/owner').status_code == 200

    deputy = app.test_client()
    with deputy.session_transaction() as session:
        session.update(user_id=99, username='deputy', role='admin', access_approved=True,
                       owner_epoch=owner.epoch(),
                       admin_token_version=admin_sessions.version('deputy'))
    assert deputy.get('/owner').status_code == 403
